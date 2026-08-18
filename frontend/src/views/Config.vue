<template>
  <div class="config-page">
    <el-card shadow="never">
      <h2>模型配置</h2>
      <p class="tip">密钥仅保存在本地 SQLite 数据库（backend/data 目录），不会上传到任何服务器。</p>
      <el-form label-width="140px" style="max-width: 680px">
        <el-divider content-position="left">大模型供应商</el-divider>
        <el-form-item label="默认供应商">
          <el-select v-model="provider" style="width: 100%">
            <el-option
              v-for="p in providers"
              :key="p.id"
              :label="p.name + '（' + p.default_model + '）'"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-for="p in keyProviders" :key="p" :label="pLabel(p)">
          <div class="key-row">
            <el-input
              v-model="keys[p]"
              type="password"
              show-password
              :placeholder="apiKeys[p] ? '已设置：' + apiKeys[p] + '（留空则不修改）' : '请输入 API Key'"
            />
            <el-link v-if="keyUrl(p)" type="primary" :href="keyUrl(p)" target="_blank" class="key-url">
              获取 Key ↗
            </el-link>
          </div>
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input v-model="models[provider]" placeholder="模型名称，留空使用默认" />
        </el-form-item>

        <el-form-item v-if="provider === 'ollama'" label="Ollama 地址">
          <el-input v-model="ollamaBaseUrl" placeholder="http://localhost:11434" />
        </el-form-item>

        <el-divider content-position="left">B站账号（可选，解锁高清字幕与受限视频）</el-divider>
        <el-form-item label="B站 Cookie">
          <div class="cookie-wrap">
            <el-input
              v-model="biliCookie"
              type="textarea"
              :rows="3"
              :placeholder="biliCookieSet ? '已设置 Cookie（留空则不修改）' : '登录 bilibili.com 后按 F12 → 应用 → Cookie，复制完整字符串粘贴到这里（如 SESSDATA=xxx; bili_jct=xxx）'"
            />
            <span class="switch-tip">仅保存在本地，用于解析字幕/受限视频；播放器清晰度已默认开启高清参数</span>
          </div>
        </el-form-item>

        <el-divider content-position="left">离线语音转写</el-divider>
        <el-form-item label="离线语音转写">
          <el-switch v-model="whisperEnabled" />
          <span class="switch-tip">无字幕视频使用本地 faster-whisper 转写（pip install faster-whisper，无需 ffmpeg）</span>
        </el-form-item>
        <el-form-item label="转写模型">
          <el-input v-model="whisperModel" style="width: 200px" placeholder="base" />
          <span class="switch-tip">tiny/base/small/medium/large，越大越准越慢</span>
        </el-form-item>
        <el-form-item label="音频语言">
          <el-input v-model="whisperLanguage" style="width: 200px" placeholder="自动检测" />
          <span class="switch-tip">如 zh / en，留空自动检测</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存配置</el-button>
          <el-button :loading="testing" @click="test">测试连接</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="如何获取 API Key"
        description="DeepSeek：platform.deepseek.com；Kimi：platform.moonshot.cn；通义千问：阿里云百炼 DashScope（需开通兼容模式）。Ollama 为本地模型，无需 Key，需先安装 Ollama 并运行 ollama serve，再拉取模型（如 ollama pull qwen2.5:7b）。长视频建议使用大窗口模型（如 Kimi moonshot-v1-32k）。"
      />
    </el-card>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'ConfigView',
  data() {
    return {
      provider: 'deepseek',
      providers: [],
      apiKeys: {},
      keys: { deepseek: '', kimi: '', qwen: '' },
      models: { deepseek: '', kimi: '', qwen: '', ollama: '' },
      ollamaBaseUrl: '',
      whisperEnabled: false,
      whisperModel: 'base',
      whisperLanguage: '',
      biliCookie: '',
      biliCookieSet: false,
      saving: false,
      testing: false
    }
  },
  computed: {
    keyProviders() {
      return this.providers
        .filter(function (p) { return p.need_key })
        .map(function (p) { return p.id })
    }
  },
  created() {
    this.load()
  },
  methods: {
    pLabel(id) {
      var found = this.providers.find(function (p) { return p.id === id })
      return (found ? found.name : id) + ' API Key'
    },
    keyUrl(id) {
      var found = this.providers.find(function (p) { return p.id === id })
      return found ? found.key_url : ''
    },
    async load() {
      try {
        var cfg = await api.get('/config')
        this.provider = cfg.provider
        this.providers = cfg.providers
        this.apiKeys = cfg.api_keys || {}
        this.models = cfg.models || {}
        this.ollamaBaseUrl = cfg.ollama_base_url || ''
        this.whisperEnabled = !!cfg.enable_whisper
        this.whisperModel = cfg.whisper_model || 'base'
        this.whisperLanguage = cfg.whisper_language || ''
        this.biliCookieSet = !!cfg.bili_cookie_set
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async save() {
      this.saving = true
      try {
        await api.post('/config/set', { key: 'provider', value: this.provider })
        var self = this
        var keyIds = this.keyProviders
        for (var i = 0; i < keyIds.length; i++) {
          var id = keyIds[i]
          if (self.keys[id]) {
            await api.post('/config/set', { key: id + '_api_key', value: self.keys[id] })
            self.keys[id] = ''
          }
        }
        await api.post('/config/set', { key: this.provider + '_model', value: this.models[this.provider] || '' })
        if (this.provider === 'ollama') {
          await api.post('/config/set', { key: 'ollama_base_url', value: this.ollamaBaseUrl || 'http://localhost:11434' })
        }
        await api.post('/config/set', { key: 'enable_whisper', value: this.whisperEnabled ? '1' : '0' })
        await api.post('/config/set', { key: 'whisper_model', value: this.whisperModel || 'base' })
        await api.post('/config/set', { key: 'whisper_language', value: this.whisperLanguage || '' })
        if (this.biliCookie && this.biliCookie.trim()) {
          await api.post('/config/set', { key: 'bili_cookie', value: this.biliCookie.trim() })
          this.biliCookie = ''
        }
        ElMessage.success('配置已保存')
        this.load()
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.saving = false
      }
    },
    async test() {
      this.testing = true
      try {
        var res = await api.post('/config/test')
        ElMessage.success('连接成功（' + res.provider + ' / ' + res.model + '）：' + res.reply)
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.testing = false
      }
    }
  }
}
</script>

<style scoped>
.tip { color: #909399; font-size: 13px; }
.switch-tip { color: #909399; font-size: 12px; margin-left: 10px; }
.key-row { display: flex; align-items: center; gap: 10px; width: 100%; }
.key-row .el-input { flex: 1; }
.key-url { flex-shrink: 0; font-size: 13px; }
.cookie-wrap { width: 100%; }
.cookie-wrap .switch-tip { display: block; margin: 6px 0 0; line-height: 1.6; }
h2 { margin-top: 0; }
</style>
