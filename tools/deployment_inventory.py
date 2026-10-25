#!/usr/bin/env python3
"""6.0 read-only host inventory, not a deployment/readiness validator. JSON to stdout."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

BASELINE = '055169fe37d5b07ce36249485d2344b9ceeb822b'
FROZEN = {
    'stream-source.js':'420e9eb8e3ed64a2ddcabc45ade00f35f7faa6c6',
    'tools/lcd_stream_fenced_api.py':'1e3341ca0841d65bad4f72bb11ed46d85a594a00',
    'PHASE6_DEPLOYMENT_PLAN.md':'e908fb85d38fd95853bf713d185bbc37cfa643b1',
}
NETWORK_FS = {'nfs','nfs4','cifs','smb3','sshfs','fuse.sshfs','9p','ceph','glusterfs'}

def git_blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return number

def origin(value):
    if any(c.isspace() for c in value) or any(c in value for c in '*?#'):
        raise argparse.ArgumentTypeError('origin must be exact, without whitespace or wildcards')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise ValueError()
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise argparse.ArgumentTypeError('expected exact HTTP(S) scheme://host[:port] origin')
    return value.rstrip('/')

def address(value):
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise argparse.ArgumentTypeError('expected an explicit IPv4 or IPv6 publish address')

def relative_file(root, value):
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('source/sentinel must be a confined relative file')
    candidate = (root/relative).resolve(strict=True)
    if not candidate.is_relative_to(root.resolve(strict=True)):
        raise ValueError('source/sentinel escapes media root')
    if not candidate.is_file():
        raise ValueError('source/sentinel is not a regular file')
    return candidate

def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
        if result.returncode:
            return {'status':'unavailable','exit_code':result.returncode}
        return {'status':'observed','value':result.stdout.strip()[:4096]}
    except FileNotFoundError:
        return {'status':'missing'}
    except (OSError, subprocess.TimeoutExpired):
        return {'status':'unavailable_or_timeout'}

def mounts(text):
    found = []
    for line in text.splitlines():
        try:
            left,right = line.split(' - ',1)
            fields = left.split()
            unescape = lambda s: re.sub(r'\\([0-7]{3})',lambda m:chr(int(m.group(1),8)),s)
            found.append({'mount_point':unescape(fields[4]),'filesystem':right.split()[0]})
        except (ValueError,IndexError):
            continue
    return found

def mount_for(path, entries):
    matching = [m for m in entries if path.is_relative_to(Path(m['mount_point']))]
    return max(matching,key=lambda m:len(Path(m['mount_point']).parts)) if matching else None

def storage(value, entries):
    if value is None:
        return {'status':'not_configured'}
    requested = Path(value).expanduser()
    if not requested.is_absolute():
        raise ValueError('storage paths must be absolute')
    try:
        path = requested.resolve(strict=True)
        if not path.is_dir():
            return {'status':'not_directory','path':str(requested)}
        stat = os.statvfs(path)
        mount = mount_for(path,entries)
        return {'status':'observed','path':str(path),'mount':mount,
            'available_bytes':stat.f_bavail*stat.f_frsize,
            'device':path.stat().st_dev,
            'current_process_access':{'read':os.access(path,os.R_OK),'write':os.access(path,os.W_OK),'traverse':os.access(path,os.X_OK)},
            'runtime_uid_permissions_verified':False}
    except (FileNotFoundError,PermissionError,OSError) as error:
        return {'status':'unavailable','path':str(requested),'reason':type(error).__name__}

def memory(text):
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] in ('MemTotal:','MemAvailable:'):
            try:
                result[fields[0][:-1]+'_bytes'] = int(fields[1])*1024
            except (IndexError,ValueError):
                pass
    return result

def read_optional(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ''

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.cwd())
    for name in ('media-root','cache-root','state-root','source','sentinel','sentinel-sha256'):
        p.add_argument('--'+name)
    for name in ('runtime-uid','runtime-gid','cache-max-bytes','min-free-bytes','memory-limit-bytes'):
        p.add_argument('--'+name,type=positive)
    p.add_argument('--origin',type=origin,action='append',default=[])
    p.add_argument('--publish-address',type=address,action='append',default=[])
    return p

def collect(args, runner=command):
    root=args.root.resolve(strict=True)
    entries=mounts(read_optional('/proc/self/mountinfo'))
    disks={name:storage(getattr(args,name+'_root'),entries) for name in ('media','cache','state')}
    pending=[];warnings=[]
    names=('media_root','cache_root','state_root','source','sentinel','sentinel_sha256','runtime_uid','runtime_gid','cache_max_bytes','min_free_bytes','memory_limit_bytes')
    inputs={name:getattr(args,name) for name in names}
    inputs.update(origins=args.origin,publish_addresses=args.publish_address)
    for name,value in inputs.items():
        if value is None or value==[]:
            pending.append('input_required:'+name)
    if args.sentinel_sha256 and not re.fullmatch('[0-9a-fA-F]{64}',args.sentinel_sha256):
        raise ValueError('sentinel-sha256 must contain exactly 64 hexadecimal characters')
    for name,data in disks.items():
        if data['status']!='observed':
            pending.append('storage_unverified:'+name)
        elif name in ('cache','state'):
            if data['mount'] is None:
                pending.append('filesystem_unidentified:'+name)
            elif data['mount']['filesystem'] in NETWORK_FS:
                pending.append('unsupported_network_filesystem:'+name)
            if args.min_free_bytes and data['available_bytes']<args.min_free_bytes:
                pending.append('insufficient_free_reserve:'+name)
    roots=[(name,Path(data['path'])) for name,data in disks.items() if data['status']=='observed']
    for index,(name,path) in enumerate(roots):
        for other_name,other in roots[index+1:]:
            if path.is_relative_to(other) or other.is_relative_to(path):
                pending.append('storage_roots_overlap:'+name+':'+other_name)
    source_info={'status':'not_verified'};identity={'status':'not_verified'}
    if disks['media']['status']=='observed':
        media=Path(disks['media']['path'])
        if args.source:
            try:
                source=relative_file(media,args.source);stat=source.stat()
                source_info={'status':'stat_only','relative_path':args.source,'size_bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,
                    'content_read':False,'duration_probed':False}
            except (ValueError,OSError) as error:
                source_info={'status':'invalid_or_unavailable','reason':str(error)}
                pending.append('source_invalid_or_unavailable')
        if args.sentinel and args.sentinel_sha256:
            try:
                sentinel=relative_file(media,args.sentinel)
                with sentinel.open('rb') as stream:
                    data=stream.read(4097)
                if len(data)>4096:
                    raise ValueError('sentinel exceeds 4096-byte bound')
                actual=hashlib.sha256(data).hexdigest()
                matched=actual==args.sentinel_sha256.lower()
                identity={'status':'matched' if matched else 'mismatch','sentinel_relative_path':args.sentinel}
                if not matched:pending.append('media_identity_mismatch')
            except (ValueError,OSError) as error:
                identity={'status':'invalid_or_unavailable','reason':str(error)}
                pending.append('media_identity_invalid_or_unavailable')
    if identity['status']!='matched':
        pending.append('media_identity_not_verified')
    frozen={}
    for name,expected in FROZEN.items():
        try:
            data=(root/name).read_bytes();actual=git_blob(data)
            frozen[name]={'expected_blob':expected,'actual_blob':actual,'matches':actual==expected}
        except OSError:
            frozen[name]={'expected_blob':expected,'actual_blob':None,'matches':False}
        if not frozen[name]['matches']:pending.append('frozen_contract_mismatch:'+name)
    tools={
        'python':{'status':'observed','value':platform.python_version()},
        'git':runner(['git','--version']),
        'node':runner(['node','--version']),
        'ffmpeg':runner(['ffmpeg','-version']),
        'ffprobe':runner(['ffprobe','-version']),
        'docker_client':runner(['docker','--version']),
        'compose':runner(['docker','compose','version']),
    }
    for name in ('ffmpeg','ffprobe','docker_client','compose'):
        if tools[name]['status']!='observed':pending.append('version_unavailable:'+name)
    if '0.0.0.0' in args.publish_address or '::' in args.publish_address:
        warnings.append('all_interfaces_selected_explicitly_not_public_authentication')
    pending.extend(['evidence_required:representative_source_peak_memory_and_headroom',
        'evidence_required:runtime_uid_permissions_and_lock_atomic_rename_support',
        'evidence_required:media_mount_identity_operator_review',
        'evidence_required:cache_quota_and_reserve_capacity_review',
        'evidence_required:stage5_browser_acceptance_record'])
    return {'schema':'wapflix-deployment-inventory-v1','checkpoint':'6.0',
        'captured_at_utc':datetime.now(timezone.utc).isoformat(),
        'reference_commit':BASELINE,'checkout_head':runner(['git','-C',str(root),'rev-parse','HEAD']),
        'deployment_ready':False,'phase6_0_complete':False,
        'scope':'Read-only observations and explicit proposals; not deployment validation or a benchmark.',
        'host':{'system':platform.system(),'release':platform.release(),'architecture':platform.machine(),'logical_cpus':os.cpu_count(),
            'observed_uid':os.getuid() if hasattr(os,'getuid') else None,'observed_gid':os.getgid() if hasattr(os,'getgid') else None,
            'memory':memory(read_optional('/proc/meminfo'))},
        'versions':tools,'frozen_sources':frozen,'operator_inputs':inputs,'storage':disks,
        'source':source_info,'media_identity':identity,'pending':sorted(set(pending)), 'warnings':warnings,
        'not_performed':['media_decode_or_probe','ffmpeg_worker_start','docker_daemon_query_or_container_changes',
            'network_requests','file_or_directory_creation','lock_or_write_permission_test','filesystem_scan','runtime_configuration_changes']}

def main(argv=None):
    p=parser();args=p.parse_args(argv)
    try:
        report=collect(args)
    except (ValueError,OSError) as error:
        p.error(str(error))
    json.dump(report,sys.stdout,indent=2);sys.stdout.write('\n')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
