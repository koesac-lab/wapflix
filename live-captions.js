/* 5A.5A: pure selection of source-time caption metadata. Not wired to playback. */
(function(root){
'use strict';
const BRAND = Symbol('WapflixPreparedCaptions');
const freeze = Object.freeze;
function prepare(metadata){
  const cues = [], warnings = [];
  let status = 'ready', parseErrorCount = 0;
  const warn = (code, index = null, count = 1) => warnings.push(freeze({code, index, count}));
  if (metadata == null) status = 'missing';
  else if (typeof metadata !== 'object' || Array.isArray(metadata)) {
    status = 'invalid'; warn('invalid_metadata');
  } else {
    if (Number.isInteger(metadata.parse_error_count) && metadata.parse_error_count >= 0) {
      parseErrorCount = metadata.parse_error_count;
      if (parseErrorCount) warn('server_parse_warnings', null, parseErrorCount);
    } else if (metadata.parse_error_count !== undefined) warn('invalid_parse_error_count');
    if (metadata.timebase !== 'source') { status = 'invalid'; warn('unsupported_timebase'); }
    if (typeof metadata.track_found !== 'boolean') { status = 'invalid'; warn('invalid_track_flag'); }
    if (!Array.isArray(metadata.cues)) { status = 'invalid'; warn('invalid_cue_list'); }
    if (status !== 'invalid') {
      status = metadata.track_found ? 'ready' : 'missing';
      if (metadata.selected_cue_count !== undefined &&
          (!Number.isInteger(metadata.selected_cue_count) || metadata.selected_cue_count !== metadata.cues.length)) {
        warn('selected_count_mismatch');
      }
      if (!metadata.track_found && metadata.cues.length) warn('cues_without_track');
      if (metadata.track_found) for (let index = 0; index < metadata.cues.length; index++) {
        const cue = metadata.cues[index];
        if (!cue || typeof cue !== 'object' ||
            typeof cue.start !== 'number' || !Number.isFinite(cue.start) || cue.start < 0 ||
            typeof cue.end !== 'number' || !Number.isFinite(cue.end) || cue.end <= cue.start ||
            typeof cue.text !== 'string') { warn('invalid_cue', index); continue; }
        const lines = cue.text.replace(/\r\n?/g, '\n').split('\n').map(line => line.trim()).filter(Boolean);
        if (!lines.length) { warn('empty_cue', index); continue; }
        cues.push(freeze({index, start: cue.start, end: cue.end, text: lines.join('\n'), lines: freeze(lines)}));
      }
    }
  }
  return freeze({[BRAND]: true, status, timebase: 'source', parseErrorCount,
    cues: freeze(cues), warnings: freeze(warnings)});
}
function requireTrack(track){
  if (!track || track[BRAND] !== true) throw TypeError('Use prepare() before selecting captions');
}
function selection(track, sourceTime, indices, lines){
  return freeze({status: track.status, sourceTime,
    activeCueIndices: freeze(indices), lines: freeze(lines), text: lines.join('\n')});
}
function selectAt(track, sourceTime){
  requireTrack(track);
  if (typeof sourceTime !== 'number' || !Number.isFinite(sourceTime) || sourceTime < 0) {
    throw RangeError('A finite non-negative source time is required');
  }
  const indices = [], lines = [], seen = new Set();
  for (const cue of track.cues) if (sourceTime >= cue.start && sourceTime < cue.end) {
    indices.push(cue.index);
    for (const line of cue.lines) if (!seen.has(line)) { seen.add(line); lines.push(line); }
  }
  return selection(track, sourceTime, indices, lines);
}
function selectFrame(track, presentedFrame){
  requireTrack(track);
  if (presentedFrame == null) return selection(track, null, [], []);
  if (typeof presentedFrame !== 'object') throw TypeError('Use the actually presented frame object');
  return selectAt(track, presentedFrame.sourceTime);
}
const api = freeze({prepare, selectAt, selectFrame});
if (typeof module !== 'undefined' && module.exports) module.exports = api;
else root.WapflixLiveCaptions = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
