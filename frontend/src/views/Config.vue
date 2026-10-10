<template>
  <div class="config-page">
    <div class="cfg-head">
      <h2>⚙️ 设置</h2>
      <p class="cfg-head-tip">
        模型密钥与偏好仅保存在本地 SQLite 数据库（数据目录见「笔记数据与学习存档」），不会上传到任何服务器。
        <span class="version-tag">当前版本 v{{ appVersion }}</span>
      </p>
      <p class="cfg-head-tip sub">
        标了 <b>立即生效</b> 的分组改完就保存；其余分组改完请点页面底部（或右下角）的 <b>保存设置</b>。
      </p>
    </div>

    <!-- 界面配色 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>界面配色</h3>
        <span class="badge-instant">立即生效</span>
      </div>
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
      <p class="hint">深色 / 浅色模式请在左下角 ☀️ / 🌙 按钮切换（手机端在顶部右上角），配色在两种模式下都会生效。</p>
    </section>

    <!-- 功能开关 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>功能开关</h3>
        <span class="badge-instant">立即生效</span>
      </div>
      <div class="switch-row">
        <div class="switch-line">
          <span class="field-label">英语听写填空</span>
          <el-switch v-model="dictationEnabled" @change="saveFeature('dictation_enabled', dictationEnabled)" />
        </div>
        <p class="hint">英语笔记页出现「听写」页签：从原视频字幕挖空，边听边填（关闭后隐藏）。</p>
      </div>
      <div class="switch-row">
        <div class="switch-line">
          <span class="field-label">同类变式题</span>
          <el-switch v-model="variantEnabled" @change="saveFeature('variant_enabled', variantEnabled)" />
        </div>
        <p class="hint">自测题卡片出现「生成变式」：AI 换数字、换情境，再出一道同知识点的题。</p>
      </div>
      <div class="switch-row">
        <div class="switch-line">
          <span class="field-label">学前诊断</span>
          <el-switch v-model="diagnosisEnabled" @change="saveFeature('diagnosis_enabled', diagnosisEnabled)" />
        </div>
        <p class="hint">打开合集后续视频前，先抽测前面几集的先修知识点，给出「可跳过 / 需先复习」建议。</p>
      </div>
    </section>

    <!-- 大模型供应商 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>大模型供应商</h3>
      </div>
      <div class="field-grid">
        <div class="field">
          <label class="field-label">默认供应商</label>
          <el-select v-model="provider" @change="markDirty">
            <el-option
              v-for="p in providers"
              :key="p.id"
              :label="p.name + '（' + p.default_model + '）'"
              :value="p.id"
            />
          </el-select>
        </div>
        <div class="field">
          <label class="field-label">模型名称</label>
          <el-input v-model="models[provider]" placeholder="留空使用默认" @input="markDirty" />
          <p class="hint">留空就用该供应商的默认模型。</p>
        </div>
        <div v-for="p in keyProviders" :key="p" class="field full">
          <label class="field-label">{{ pLabel(p) }}</label>
          <div class="inline-row">
            <el-input
              v-model="keys[p]"
              type="password"
              show-password
              :placeholder="apiKeys[p] ? '已保存 ' + apiKeys[p] + '（留空表示不修改）' : '粘贴你的 API Key'"
              @input="markDirty"
              @blur="saveKey(p)"
            />
            <el-link v-if="keyUrl(p)" type="primary" :href="keyUrl(p)" target="_blank" class="key-url">
              获取 Key ↗
            </el-link>
          </div>
        </div>
        <div v-if="provider === 'ollama'" class="field full">
          <label class="field-label">Ollama 地址</label>
          <el-input v-model="ollamaBaseUrl" placeholder="http://localhost:11434" @input="markDirty" />
        </div>
      </div>

      <el-collapse class="key-help">
        <el-collapse-item title="如何获取 API Key？（点开查看）" name="help">
          <ul class="key-help-list">
            <li><b>DeepSeek</b>：platform.deepseek.com，默认 <code>deepseek-v4-pro</code>，视觉公式识别自动改用 <code>deepseek-flash</code>。</li>
            <li><b>Kimi（Moonshot）</b>：platform.kimi.com，默认 <code>kimi-k2.6</code>，支持视觉与 256k 长上下文。</li>
            <li><b>通义千问</b>：阿里云百炼 DashScope（兼容模式），视觉用 <code>qwen-vl-max</code>。</li>
            <li><b>Ollama</b>：本地模型，无需 Key。先安装 Ollama 并运行 <code>ollama serve</code>，再 <code>ollama pull qwen2.5:7b</code>。</li>
            <li><b>长视频</b>建议用大上下文窗口模型（如 Kimi <code>kimi-k2.6</code>）。</li>
          </ul>
        </el-collapse-item>
      </el-collapse>
    </section>

    <!-- B站账号 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>B站账号</h3>
        <span class="cfg-sub">可选，用于解锁登录后可见的字幕与受限视频</span>
      </div>
      <div class="field-grid">
        <div class="field full">
          <label class="field-label">B站 Cookie</label>
          <el-input
            v-model="biliCookie"
            type="textarea"
            :rows="3"
            :placeholder="biliCookieSet ? '已保存 Cookie（留空表示不修改）' : '登录 bilibili.com 后按 F12 → 应用(Application) → Cookie → https://www.bilibili.com，整段复制粘贴到这里，必须包含 SESSDATA=...'"
            @input="markDirty"
          />
          <p class="hint">
            仅保存在本地。作用是拿到「登录后才可见」的官方字幕 / AI 字幕与受限视频；不配也能用，只是这类字幕拿不到。
          </p>
          <div class="inline-row">
            <el-button size="small" :loading="cookieChecking" @click="checkCookie">验证登录状态</el-button>
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
      </div>
    </section>

    <!-- 离线语音转写 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>离线语音转写</h3>
        <span class="cfg-sub">没有字幕的视频用它兜底</span>
      </div>
      <div class="field-grid">
        <div class="field full">
          <div class="switch-line">
            <span class="field-label">启用离线语音转写</span>
            <el-switch v-model="whisperEnabled" @change="saveFeature('enable_whisper', whisperEnabled)" />
          </div>
          <p class="hint">开启后，没有字幕的视频会用本地 faster-whisper 转写（无需 ffmpeg）。</p>
        </div>
        <div class="field">
          <label class="field-label">转写模型</label>
          <el-input v-model="whisperModel" placeholder="base" @input="markDirty" />
          <p class="hint">tiny / base / small / medium / large，越大越准越慢。</p>
        </div>
        <div class="field">
          <label class="field-label">音频语言</label>
          <el-input v-model="whisperLanguage" placeholder="自动检测" @input="markDirty" />
          <p class="hint">如 zh / en，留空自动检测。</p>
        </div>
        <div class="field full">
          <label class="field-label">模型下载源</label>
          <el-select
            v-model="hfEndpoint"
            filterable
            allow-create
            default-first-option
            @change="saveFeatureValue('hf_endpoint', hfEndpoint === 'auto' ? '' : hfEndpoint)"
          >
            <el-option label="自动（先官方，失败自动切国内镜像）" value="auto" />
            <el-option label="国内镜像 hf-mirror.com（推荐）" value="mirror" />
            <el-option label="HuggingFace 官方源" value="official" />
          </el-select>
          <p class="hint">
            语音识别模型托管在 huggingface.co，国内直连经常「连接超时」。首次转写会先下载模型（base 约 150MB），失败时会给出明确处理办法。
            <template v-if="hfEndpointEnv">当前环境变量 HF_ENDPOINT = {{ hfEndpointEnv }}</template>
          </p>
        </div>
      </div>
    </section>

    <!-- 合集批量任务 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>合集批量任务</h3>
      </div>
      <div class="field-grid">
        <div class="field">
          <label class="field-label">同时处理集数</label>
          <el-input-number v-model="collectionConcurrency" :min="1" :max="4" @change="markDirty" />
          <p class="hint">并发 1-4，越大越快但越容易触发限流；本地 Whisper 转写建议保持 1。</p>
        </div>
      </div>
    </section>

    <!-- 笔记数据与学习存档 -->
    <section class="cfg-card">
      <div class="cfg-title">
        <h3>笔记数据与学习存档</h3>
        <span class="cfg-sub">独立于程序目录，升级或重装都不会丢</span>
      </div>
      <div class="field">
        <label class="field-label">数据目录</label>
        <div class="inline-row">
          <el-input :model-value="dataInfo.data_dir || '读取中…'" readonly />
          <el-button size="small" @click="copyDataDir">复制路径</el-button>
          <el-button size="small" @click="openDataDir">打开目录</el-button>
        </div>
        <p class="hint">
          数据库、Markdown 笔记与关键帧截图都在这里。当前 {{ dataInfo.note_count || 0 }} 篇笔记，占用约
          {{ formatSize((dataInfo.db_size || 0) + (dataInfo.notes_bytes || 0)) }}。
          <template v-if="dataInfo.env_override">（当前目录由环境变量 BILI_DATA_DIR 指定）</template>
        </p>
      </div>
      <div class="field">
        <label class="field-label">学习存档</label>
        <div class="inline-row">
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
        <p class="hint">
          同一个视频（同 BV + 同分 P）已存在时自动跳过，只补充新的笔记、错题、复习计划、合集任务与关键帧截图；
          不会覆盖你本机的设置与 API Key。
        </p>
        <div v-if="lastImport" class="archive-result">
          上次导入：新增 {{ lastImport.notes_added }} 篇笔记（跳过重复 {{ lastImport.notes_skipped }} 篇）、
          错题 {{ lastImport.wrong_added }}、复习计划 {{ lastImport.plans_added }}、合集任务 {{ lastImport.collections_added }}、截图 {{ lastImport.frames_copied }} 张。
          <div v-if="lastImport.warnings && lastImport.warnings.length" class="archive-warn">
            {{ lastImport.warnings.join('；') }}
          </div>
        </div>
      </div>
    </section>

    <!-- 底部保存条：原来这个"保存配置"按钮被误删，导致 API Key / Cookie / 模型 / 并发数都存不下来 -->
    <div class="cfg-actions">
      <span class="cfg-actions-hint" :class="{ warn: dirty }">
        {{ dirty ? '● 有未保存的修改，记得点右侧「保存设置」' : '所有修改已保存' }}
      </span>
      <el-button :loading="testing" @click="test">测试连接</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
    </div>
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
      origModels: {},
      savedKeys: {},
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
      dirty: false,
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
    markDirty() {
      this.dirty = true
    },
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
        // 后端返回的是 deepseek_api_key 这种列表键名，这里统一转成 { deepseek: 'sk-****1234' }
        // （原先前端直接用 apiKeys[providerId] 取值，永远取不到，"已设置 sk-****" 的提示因此从没出现过）
        var rawKeys = cfg.api_keys || {}
        var normalized = {}
        Object.keys(rawKeys).forEach(function (k) {
          normalized[k.replace(/_api_key$/, '')] = rawKeys[k]
        })
        this.apiKeys = normalized
        this.models = cfg.models || {}
        this.origModels = JSON.parse(JSON.stringify(this.models))
        this.ollamaBaseUrl = cfg.ollama_base_url || ''
        this.whisperEnabled = !!cfg.enable_whisper
        this.whisperModel = cfg.whisper_model || 'base'
        this.whisperLanguage = cfg.whisper_language || ''
        // 空字符串会被 el-select 当成"未选择"（显示 placeholder），这里用 auto 当哨兵值表示"自动"
        this.hfEndpoint = cfg.hf_endpoint || 'auto'
        this.hfEndpointEnv = cfg.hf_endpoint_env || ''
        this.biliCookieSet = !!cfg.bili_cookie_set
        this.biliCookieHasSessdata = !!cfg.bili_cookie_has_sessdata
        this.collectionConcurrency = Number(cfg.collection_concurrency) || 2
        this.dictationEnabled = cfg.dictation_enabled !== false
        this.variantEnabled = cfg.variant_enabled !== false
        this.diagnosisEnabled = cfg.diagnosis_enabled !== false
        this.dirty = false
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
    // API Key 失焦即自动保存：即使忘记点「保存设置」也不会白填
    async saveKey(id) {
      var value = (this.keys[id] || '').trim()
      if (!value) return
      try {
        await api.post('/config/set', { key: id + '_api_key', value: value })
        this.keys[id] = ''
        this.savedKeys[id] = true
        ElMessage.success('API Key 已自动保存')
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
            self.savedKeys[id] = true
          }
        }
        // 只写被改动过的模型名，避免把默认值也固化进设置
        var provIds = ['deepseek', 'kimi', 'qwen', 'ollama']
        for (var j = 0; j < provIds.length; j++) {
          var pid = provIds[j]
          var val = self.models[pid] || ''
          if (val !== (self.origModels[pid] || '')) {
            await api.post('/config/set', { key: pid + '_model', value: val })
          }
        }
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
        ElMessage.success('设置已保存')
        await this.load()
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
/* ---------- 页面骨架 ---------- */
.config-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 4px 4px 20px;
}
.cfg-head { margin-bottom: 16px; }
.cfg-head h2 { margin: 0 0 6px; font-size: 20px; }
.cfg-head-tip { margin: 0; color: var(--c-text-3); font-size: 13px; line-height: 1.7; }
.cfg-head-tip.sub { margin-top: 6px; }
.version-tag {
  display: inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 999px;
  background: var(--c-primary-soft); color: var(--c-primary); font-size: 12px;
}

/* ---------- 分区卡片 ---------- */
.cfg-card {
  background: var(--c-bg-elev);
  border: 1px solid var(--c-border);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 14px;
  box-shadow: var(--c-shadow-card);
}
.cfg-title {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px; flex-wrap: wrap;
}
.cfg-title h3 {
  margin: 0; font-size: 15px; font-weight: 700; color: var(--c-text);
  display: flex; align-items: center; gap: 9px;
}
.cfg-title h3::before {
  content: ''; width: 3px; height: 15px; border-radius: 2px;
  background: var(--c-primary); flex-shrink: 0;
}
.cfg-sub { font-size: 12px; color: var(--c-text-3); }
.badge-instant {
  margin-left: auto; font-size: 11.5px; padding: 2px 9px; border-radius: 999px;
  background: var(--c-success-soft); color: var(--c-success); white-space: nowrap;
}

/* ---------- 字段：标签在控件上方，长标签也不会错位 ---------- */
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 22px;
}
.field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.field.full { grid-column: 1 / -1; }
.field-label { font-size: 13px; font-weight: 600; color: var(--c-text-2); }
.hint { margin: 0; font-size: 12px; line-height: 1.65; color: var(--c-text-3); }

/* ---------- 开关行 ---------- */
.switch-row { padding: 10px 0; border-bottom: 1px dashed var(--c-border-light); }
.switch-row:last-child { border-bottom: none; padding-bottom: 0; }
.switch-line {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-bottom: 5px;
}

/* ---------- 一行内 图标 + 输入 ---------- */
.inline-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.inline-row .el-input { flex: 1 1 260px; min-width: 0; }
.key-url { flex-shrink: 0; font-size: 13px; }

/* ---------- 配色卡 ---------- */
.palette-row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px; margin-bottom: 10px;
}
.palette-card {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px 12px; border-radius: 11px;
  border: 1px solid var(--c-border); background: var(--c-bg-elev);
  cursor: pointer; transition: all .15s;
}
.palette-card:hover { box-shadow: var(--c-shadow-hover); transform: translateY(-1px); }
.palette-card.active { border-color: var(--c-primary); box-shadow: 0 0 0 2px var(--c-primary-soft); }
.palette-dots { display: flex; gap: 5px; }
.palette-dots i {
  width: 22px; height: 22px; border-radius: 50%;
  display: inline-block; border: 1px solid rgba(0, 0, 0, .08);
}
.palette-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
.palette-desc { font-size: 12px; color: var(--c-text-3); line-height: 1.4; }

/* ---------- API Key 获取说明（折叠，长文案不再糊成一大段） ---------- */
.key-help { margin-top: 14px; border-top: 1px solid var(--c-border-light); }
.key-help :deep(.el-collapse-item__header) {
  background: transparent; border-bottom: none;
  font-size: 13px; color: var(--c-text-2); height: 42px;
}
.key-help :deep(.el-collapse-item__wrap) { background: transparent; border-bottom: none; }
.key-help-list { margin: 0; padding-left: 18px; font-size: 12.5px; line-height: 1.95; color: var(--c-text-2); }
.key-help-list code {
  background: var(--c-bg-soft); padding: 1px 5px; border-radius: 4px; font-size: 12px;
}

/* ---------- B站 Cookie ---------- */
.cookie-result { margin-top: 8px; }

/* ---------- 学习存档 ---------- */
.archive-drop {
  width: 100%; padding: 16px 14px; text-align: center;
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

/* ---------- 底部保存条（吸底，随时可点） ---------- */
.cfg-actions {
  position: sticky;
  bottom: 0;
  z-index: 5;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--c-border);
  border-radius: 14px;
  background: var(--c-bg-elev);
  box-shadow: 0 -2px 12px rgba(23, 32, 38, .06);
}
.cfg-actions-hint { margin-right: auto; font-size: 12.5px; color: var(--c-text-3); }
.cfg-actions-hint.warn { color: var(--c-accent); font-weight: 600; }

/* ---------- 窄屏 ---------- */
@media (max-width: 760px) {
  .field-grid { grid-template-columns: minmax(0, 1fr); }
  .cfg-card { padding: 14px; }
  .cfg-actions { flex-direction: column; align-items: stretch; }
  .cfg-actions-hint { margin-right: 0; }
}
</style>
