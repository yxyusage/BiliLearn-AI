<template>
  <div class="config-page">
    <el-card shadow="never">
      <h2>⚙️ 设置</h2>
      <p class="tip">模型密钥与偏好仅保存在本地 SQLite 数据库（backend/data 目录），不会上传到任何服务器。</p>

      <el-form label-width="140px" style="max-width: 720px">
        <el-divider content-position="left">界面配色</el-divider>
        <el-form-item label="主题色">
          <div class="palette-row">
            <div
              v-for="p in palettes"
              :key="p.id"
              class="palette-card"
              :class="{ active: palette === p.id }"
              @click="pickPalette(p.id)"
            >
              <span class="palette-dots">
                <i :style="{ background: p.swatch.main }"></i>
                <i :style="{ background: p.swatch.soft }"></i>
                <i :style="{ background: p.swatch.bg }"></i>
              </span>
              <span class="palette-name">{{ p.name }}</span>
              <span class="palette-desc">{{ p.desc }}</span>
            </div>
          </div>
          <span class="switch-tip">深色 / 浅色模式请在右上角 ☀️/🌙 按钮切换，配色两种模式都会生效</span>
        </el-form-item>

        <el-divider content-position="left">功能开关</el-divider>
        <el-form-item label="英语听写填空">
          <el-switch v-model="dictationEnabled" @change="saveFeature('dictation_enabled', dictationEnabled)" />
          <span class="switch-tip">英语笔记页出现「听写」页签：从原视频字幕挖空，边听边填（关闭后隐藏）</span>
        </el-form-item>
        <el-form-item label="同类变式题">
          <el-switch v-model="variantEnabled" @change="saveFeature('variant_enabled', variantEnabled)" />
          <span class="switch-tip">自测题卡片出现「生成变式」：AI 换数字、换情境再出一道同知识点题</span>
        </el-form-item>
        <el-form-item label="学前诊断">
          <el-switch v-model="diagnosisEnabled" @change="saveFeature('diagnosis_enabled', diagnosisEnabled)" />
          <span class="switch-tip">打开合集后续视频前，先抽测前面几集的先修知识点，给出「可跳过/需先复习」建议</span>
        </el-form-item>

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
          <el-switch v-model="whisperEnabled" @change="saveFeature('enable_whisper', whisperEnabled)" />
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

        <el-divider content-position="left">合集批量任务</el-divider>
        <el-form-item label="同时处理集数">
          <el-input-number v-model="collectionConcurrency" :min="1" :max="4" size="small" style="width: 130px" />
          <span class="switch-tip">并发 1-4，越大越快但越容易触发限流；本地 Whisper 转写建议保持 1</span>
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
        description="DeepSeek：platform.deepseek.com（默认 deepseek-v4-pro，视觉公式识别自动用 deepseek-flash）；Kimi：platform.kimi.com（默认 kimi-k2.6，支持视觉与 256k 长上下文）；通义千问：阿里云百炼 DashScope（兼容模式，视觉用 qwen-vl-max）。Ollama 为本地模型，无需 Key，需先安装 Ollama 并运行 ollama serve，再拉取模型（如 ollama pull qwen2.5:7b）。长视频建议使用大窗口模型（如 Kimi kimi-k2.6）。"
      />
    </el-card>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import { theme, setPalette } from '../utils/theme'

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
      collectionConcurrency: 2,
      dictationEnabled: true,
      variantEnabled: true,
      diagnosisEnabled: true,
      saving: false,
      testing: false,
      palette: theme.palette,
      palettes: [
        { id: 'paper', name: '纸墨青', desc: '墨青 + 暖纸，学术书卷气', swatch: { main: '#0d7e70', soft: '#e6f4f1', bg: '#f6f5f1' } },
        { id: 'ocean', name: '海盐蓝', desc: '冷静蓝调，适合长时间阅读', swatch: { main: '#2563eb', soft: '#e8effd', bg: '#f5f7fb' } },
        { id: 'sunset', name: '秋日橙', desc: '暖陶土色，专注学习的小暖窝', swatch: { main: '#bf5b2d', soft: '#fbeee7', bg: '#faf6f0' } }
      ]
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
    pickPalette(id) {
      this.palette = id
      setPalette(id)
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
        this.collectionConcurrency = Number(cfg.collection_concurrency) || 2
        this.dictationEnabled = cfg.dictation_enabled !== false
        this.variantEnabled = cfg.variant_enabled !== false
        this.diagnosisEnabled = cfg.diagnosis_enabled !== false
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async saveFeature(key, value) {
      try {
        await api.post('/config/set', { key: key, value: value ? '1' : '0' })
        ElMessage.success('已保存')
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
        await api.post('/config/set', { key: 'whisper_model', value: this.whisperModel || 'base' })
        await api.post('/config/set', { key: 'whisper_language', value: this.whisperLanguage || '' })
        if (this.biliCookie && this.biliCookie.trim()) {
          await api.post('/config/set', { key: 'bili_cookie', value: this.biliCookie.trim() })
          this.biliCookie = ''
        }
        await api.post('/config/set', {
          key: 'collection_concurrency',
          value: String(Math.min(4, Math.max(1, this.collectionConcurrency || 2)))
        })
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
.tip { color: var(--c-text-3); font-size: 13px; }
.switch-tip { color: var(--c-text-3); font-size: 12px; margin-left: 10px; line-height: 1.6; }
.key-row { display: flex; align-items: center; gap: 10px; width: 100%; }
.key-row .el-input { flex: 1; }
.key-url { flex-shrink: 0; font-size: 13px; }
.cookie-wrap { width: 100%; }
.cookie-wrap .switch-tip { display: block; margin: 6px 0 0; line-height: 1.6; }
h2 { margin-top: 0; }

.palette-row { display: flex; gap: 10px; flex-wrap: wrap; }
.palette-card {
  display: flex; flex-direction: column; gap: 4px;
  width: 150px; padding: 10px 12px; border-radius: 10px;
  border: 1px solid var(--c-border); background: var(--c-bg-elev);
  cursor: pointer; transition: all .15s;
}
.palette-card:hover { box-shadow: var(--c-shadow-hover); transform: translateY(-1px); }
.palette-card.active { border-color: var(--c-primary); box-shadow: 0 0 0 2px var(--c-primary-soft); }
.palette-dots { display: flex; gap: 5px; }
.palette-dots i { width: 22px; height: 22px; border-radius: 50%; display: inline-block; border: 1px solid rgba(0,0,0,.08); }
.palette-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
.palette-desc { font-size: 12px; color: var(--c-text-3); line-height: 1.4; }
</style>
