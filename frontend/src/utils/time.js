// HH:MM:SS -> 秒
export function hmsToSeconds(hms) {
  if (!hms) return 0
  if (typeof hms === 'number') return hms
  var s = String(hms).trim()
  var parts = s.split(':')
  var nums = []
  for (var i = 0; i < parts.length; i++) {
    nums.push(parseFloat(parts[i]) || 0)
  }
  if (nums.length === 3) return nums[0] * 3600 + nums[1] * 60 + nums[2]
  if (nums.length === 2) return nums[0] * 60 + nums[1]
  return nums[0] || 0
}

// 紧凑 HHMMSS -> 秒（脑图节点 id 用）
export function hmsCompactToSeconds(compact) {
  var s = String(compact || '').replace(/[^0-9]/g, '')
  while (s.length < 6) s = '0' + s
  return parseInt(s.slice(0, 2), 10) * 3600 + parseInt(s.slice(2, 4), 10) * 60 + parseInt(s.slice(4, 6), 10)
}

// 秒 -> HH:MM:SS
export function secondsToHms(seconds) {
  var s = Math.max(0, Math.floor(seconds || 0))
  var h = Math.floor(s / 3600)
  var m = Math.floor((s % 3600) / 60)
  var sec = s % 60
  var pad = function (n) { return (n < 10 ? '0' : '') + n }
  return pad(h) + ':' + pad(m) + ':' + pad(sec)
}
