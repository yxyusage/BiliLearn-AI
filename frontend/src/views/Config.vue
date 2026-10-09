<template>
  <div class="config-page">
    <el-card shadow="never">
      <h2>⚙️ 设置</h2>
      <p class="tip">
        模型密钥与偏好仅保存在本地 SQLite 数据库（数据目录见页面底部「笔记数据与学习存档」），不会上传到任何服务器。
        <span class="version-tag">当前版本 v{{ appVersion }}</span>
      </p>

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
          <span class="switch-tip">深色 / 浅色模式请在左下角 ☀️/🌙 按钮切换（手机端在顶部右上角），配色两种模式都会生效</span>
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
              :placeholder="biliCookieSet ? '已设置 Cookie（留空则不修改）' : '登录 bilibili.com 后按 F12 → 应用(Application) → Cookie → https://www.bilibili.com，整段复制粘贴到这里，必须包含 SESSDATA=...'"
            />
            <div class="cookie-actions">
              <el-button size="small" :loading="cookieChecking" @click="checkCookie">验证登录状态</el-button>
              <span class="switch-tip">
                仅保存在本地。作用是拿到「登录后才可见」的官方字幕 / AI 字幕与受限视频；
                不配也能用，只是这类字幕拿不到。
              </span>
            </div>
            <el-alert
              v-if="cookieResult"
              :title="cookieResult.message"
              :type="cookieResult.logged_in ? 'success' : (cookieResult.has_cookie ? 'warning' : 'info')"
              :closable="false"
              show-icon
              class="cookie-result"
            />
            <el-alert
              v-else-if="biliCookieSet && !biliCookieHasSessdata"
              title="已保存的 Cookie 里没有 SESSDATA —— 那只是游客身份，等于没配"
              description="SESSDATA 是 B站 的登录凭证，缺了它拿不到任何登录后可见的字幕。请重新按上面的路径复制一次。"
              type="warning"
              :closable="false"
              show-icon
              class="cookie-result"
            />
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
        <el-form-item label="模型下载源">
          <el-select
            v-model="hfEndpoint"
            style="width: 280px"
            filterable
            allow-create
            default-first-option
            @change="saveFeatureValue('hf_endpoint', hfEndpoint)"
          >
            <el-option label="自动（先官方，失败自动切国内镜像）" value="" />
            <el-option label="国内镜像 hf-mirror.com（推荐）" value="mirror" />
            <el-option label="HuggingFace 官方源" value="official" />
          </el-select>
          <span class="switch-tip">
            语音识别模型托管在 huggingface.co，国内直连经常「连接超时」。首次转写会先下载模型，失败时会给出明确提示和处理办法。
            <template v-if="hfEndpointEnv">当前环境变量 HF_ENDPOINT = {{ hfEndpointEnv }}</template>
          </span>
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

        <el-divider content-position="left">笔记数据与学习存档</el-divider>
        <el-form-item label="数据目录">
          <div class="data-dir-row">
            <el-input :model-value="dataInfo.data_dir || '读取中…'" readonly />
            <el-button size="small" @click="copyDataDir">复制路径</el-button>
            <el-button size="small" @click="openDataDir">打开目录</el-button>
          </div>
          <span class="switch-tip block-tip">
            数据库、Markdown 笔记与关键帧截图都在这里，独立于程序目录：升级或重新下载新版本都不会丢。
            当前 {{ dataInfo.note_count || 0 }} 篇笔记，占用约 {{ formatSize((dataInfo.db_size || 0) + (dataInfo.notes_bytes || 0)) }}。
            <template v-if="dataInfo.env_override">（当前目录由环境变量 BILI_DATA_DIR 指定）</template>
          </span>
        </el-form-item>

        <el-form-item label="学习存档">
          <div class="archive-row">
            <el-button type="primary" plain :loading="exporting" @click="exportArchive">导出学习存档</el-button>
            <el-button :loading="importing" @click="pickArchive">导入 / 合并存档</el-button>
            <input
              ref="archiveInput"
              type="file"
              accept=".db,.sqlite,.sqlite3,.zip"
              style="display:none"
              @change="onArchivePicked"
            />
          </div>
          <div
            class="archive-drop"
            :class="{ over: archiveDragOver }"
            @dragenter.prevent="archiveDragOver = true"
            @dragover.prevent="archiveDragOver = true"
            @dragleave.prevent="archiveDragOver = false"
            @drop.prevent="onArchiveDrop"
          >
            <template v-if="importing">正在合并导入，请勿关闭页面…</template>
            <template v-else>也可以把 <b>bililearn.db</b> 或导出的存档 zip 拖到这里合并导入</template>
          </div>
          <span class="switch-tip block-tip">
            同一个视频（同 BV + 同分 P）已存在时自动跳过，只补充新的笔记、错题、复习计划、合集任务与关键帧截图；
            不会覆盖你本机的设置与 API Key。
          </span>
          <div v-if="lastImport" class="archive-result">
            上次导入：新增 {{ lastImport.notes_added }} 篇笔记（跳过重复 {{ lastImport.notes_skipped }} 篇）、
            错题 {{ lastImport.wrong_added }}、复习计划 {{ lastImport.plans_added }}、合集任务 {{ lastImport.collections_added }}、截图 {{ lastImport.frames_copied }} 张。
            <div v-if="lastImport.warnings && lastImport.warnings.length" class="archive-warn">
              {{ lastImport.warnings.join('；') }}
            </div>
          </div>
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
      appVersion: typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '',
      provider: 'deepseek',
      providers: [],
      apiKeys: {},
      keys: { deepseek: '', kimi: '', qwen: '' },
      models: { deepseek: '', kimi: '', qwen: '', ollama: '' },
      ollamaBaseUrl: '',
      whisperEnabled: false,
      whisperModel: 'base',
      whisperLanguage: '',
      hfEndpoint: '',
      hfEndpointEnv: '',
      biliCookie: '',
      biliCookieSet: false,
      biliCookieHasSessdata: false,
      cookieChecking: false,
      cookieResult: null,
      collectionConcurrency: 2,
      dictationEnabled: true,
      variantEnabled: true,
      diagnosisEnabled: true,
      saving: false,
      testing: false,
      // 数据目录与学习存档
      dataInfo: { data_dir: '', db_size: 0, notes_bytes: 0, note_count: 0, env_override: false },
      exporting: false,
      importing: false,
      archiveDragOver: false,
      lastImport: null,
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
    this.loadDataInfo()
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
        this.hfEndpoint = cfg.hf_endpoint || ''
        this.hfEndpointEnv = cfg.hf_endpoint_env || ''
        this.biliCookieSet = !!cfg.bili_cookie_set
        this.biliCookieHasSessdata = !!cfg.bili_cookie_has_sessdata
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
    async saveFeatureValue(key, value) {
      try {
        await api.post('/config/set', { key: key, value: value || '' })
        ElMessage.success('已保存，下次转写生效')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async checkCookie() {
      this.cookieChecking = true
      try {
        var typed = (this.biliCookie || '').trim()
        this.cookieResult = await api.post('/config/verify-cookie', typed ? { cookie: typed } : {})
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.cookieChecking = false
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
          this.cookieResult = null
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
    formatSize(bytes) {
      var n = Number(bytes) || 0
      if (n >= 1024 * 1024 * 1024) return (n / 1024 / 1024 / 1024).toFixed(2) + ' GB'
      if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB'
      if (n >= 1024) return Math.round(n / 1024) + ' KB'
      return n + ' B'
    },
    async loadDataInfo() {
      try {
        this.dataInfo = await api.get('/data/info')
      } catch (e) { /* 读取失败不影响其他设置 */ }
    },
    copyDataDir() {
      var text = this.dataInfo.data_dir || ''
      if (!text) return
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          ElMessage.success('路径已复制')
        }).catch(function () {
          ElMessage.warning('复制失败，请手动选择输入框内容')
        })
      } else {
        ElMessage.warning('当前浏览器不支持自动复制，请手动选择输入框内容')
      }
    },
    async openDataDir() {
      try {
        await api.post('/data/open')
        ElMessage.success('已在文件管理器中打开数据目录')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async exportArchive() {
      this.exporting = true
      try {
        var resp = await fetch('/api/data/export')
        if (!resp.ok) throw new Error('导出失败（HTTP ' + resp.status + '）')
        var blob = await resp.blob()
        var disposition = resp.headers.get('Content-Disposition') || ''
        var matched = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^;"']+)/i)
        var name = matched ? decodeURIComponent(matched[1]) : 'BiliLearn-学习存档.zip'
        var link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = name
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setTimeout(function () { URL.revokeObjectURL(link.href) }, 1000)
        ElMessage.success('学习存档已开始下载')
      } catch (e) {
        ElMessage.error(e.message || String(e))
      } finally {
        this.exporting = false
      }
    },
    pickArchive() {
      if (this.$refs.archiveInput) this.$refs.archiveInput.click()
    },
    onArchivePicked(e) {
      var files = e.target.files || []
      var file = files[0]
      e.target.value = ''
      if (file) this.importArchive(file)
    },
    onArchiveDrop(e) {
      this.archiveDragOver = false
      var files = (e.dataTransfer && e.dataTransfer.files) || []
      if (!files.length) return
      this.importArchive(files[0])
    },
    async importArchive(file) {
      this.importing = true
      try {
        var form = new FormData()
        form.append('file', file, file.name)
        var res = await api.post('/data/import', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 0
        })
        this.lastImport = res
        this.loadDataInfo()
        ElMessage.success('导入完成：新增 ' + res.notes_added + ' 篇笔记，跳过重复 ' + res.notes_skipped + ' 篇')
      } catch (e) {
        ElMessage.error('导入失败：' + e.message)
      } finally {
        this.importing = false
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
.version-tag {
  display: inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 999px;
  background: var(--c-primary-soft); color: var(--c-primary); font-size: 12px;
}
.switch-tip { color: var(--c-text-3); font-size: 12px; margin-left: 10px; line-height: 1.6; }
.key-row { display: flex; align-items: center; gap: 10px; width: 100%; }
.key-row .el-input { flex: 1; }
.key-url { flex-shrink: 0; font-size: 13px; }
.cookie-wrap { width: 100%; }
.cookie-wrap .switch-tip { margin: 0; }
.cookie-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 8px; }
.cookie-result { margin-top: 8px; }
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

/* 数据目录与学习存档 */
.data-dir-row { display: flex; align-items: center; gap: 8px; width: 100%; }
.data-dir-row .el-input { flex: 1; }
.block-tip { display: block; margin: 6px 0 0; }
.archive-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.archive-drop {
  margin-top: 10px; width: 100%; padding: 16px 14px; text-align: center;
  border: 1.5px dashed var(--c-border); border-radius: 12px;
  background: var(--c-bg-soft); color: var(--c-text-3); font-size: 13px;
  transition: border-color .15s, background .15s, color .15s;
}
.archive-drop.over { border-color: var(--c-primary); background: var(--c-primary-soft); color: var(--c-primary); }
.archive-result {
  margin-top: 10px; width: 100%; padding: 8px 12px; border-radius: 8px;
  background: var(--c-success-soft); color: var(--c-text-2); font-size: 12px; line-height: 1.7;
}
.archive-warn { color: var(--c-danger); margin-top: 4px; }
</style>
