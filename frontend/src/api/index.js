import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 600000
})

api.interceptors.response.use(
  function (res) { return res.data },
  function (err) {
    var detail = ''
    if (err.response && err.response.data) {
      if (typeof err.response.data.detail === 'string') detail = err.response.data.detail
      else detail = JSON.stringify(err.response.data.detail || err.response.data)
    }
    var msg = detail || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

export default api
