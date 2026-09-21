<template>
  <div class="note-detail" v-loading="loading">
    <!-- 生成中 -->
    <div v-if="status === 'processing'" class="status-box">
      <el-result icon="info" title="AI 正在生成笔记">
        <template #sub-title>
          <p class="stage-text">{{ stageText || '正在初始化...' }}</p>
          <p class="stage-tip">通常需要 1-5 分钟（无字幕转写会更久）。进度按实际耗时计算，切换页面/刷新后再回来也不会重置。</p>
          <el-progress :percentage="progressPercent" />
        </template>
        <template #extra>
          <el-button @click="$router.push('/history')">去历史笔记查看</el-button>
        </template>
      </el-result>
    </div>

    <!-- 失败 -->
    <div v-else-if="status === 'failed'" class="status-box">
      <el-result icon="error" title="笔记生成失败">
        <template #sub-title><p class="err-text">{{ error }}</p></template>
        <template #extra>
          <el-button type="primary" :loading="retrying" @click="retryGenerate">重新生成</el-button>
          <el-popconfirm title="删除这条失败记录？" @confirm="deleteNote">
            <template #reference>
              <el-button type="danger" plain>删除记录</el-button>
            </template>
          </el-popconfirm>
          <el-button @click="$router.push('/')">返回首页</el-button>
        </template>
      </el-result>
    </div>

    <!-- 完成 -->
    <template v-else-if="status === 'done'">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-radio-group v-model="layoutMode" size="small">
            <el-radio-button value="split">左右分栏</el-radio-button>
            <el-radio-button value="top">视频置顶</el-radio-button>
          </el-radio-group>
          <span v-if="layoutMode === 'split'" class="drag-tip">↔ 拖动中间分隔条调整视频宽度</span>
        </div>
        <div class="toolbar-actions">
          <el-button size="small" @click="download('markdown')">导出 Markdown</el-button>
          <el-button size="small" @click="download('pdf')">导出 PDF</el-button>
          <el-button size="small" @click="download('docx')">导出 Word</el-button>
          <el-button size="small" @click="download('xmind')">导出 XMind</el-button>
          <el-button v-if="hasWords" size="small" @click="download('anki')">Anki 卡片</el-button>
          <el-button v-if="hasWords" size="small" @click="download('anki.csv')">CSV</el-button>
          <el-button size="small" type="primary" plain @click="chatVisible = true">💬 AI 答疑</el-button>
        </div>
      </div>

      <div ref="splitLayout" class="layout" :class="[layoutMode, { dragging: dragging }]" :style="{ '--vw': layoutMode === 'split' ? leftWidth + '%' : '0%' }">
        <div class="video-panel" :style="videoPanelStyle">
          <div class="sticky-video">
            <VideoPlayer ref="player" :bvid="bvid" :page="page" />
            <div class="meta-line">
              <el-tag size="small" type="info" effect="plain">{{ bvid }}</el-tag>
              <span class="note-title">{{ title }}</span>
              <el-button size="small" text type="warning" @click="openConfusionAtTime">
                🙋 没懂（{{ lastJumpLabel }}）
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="layoutMode === 'split'" class="split-divider" @pointerdown="startDrag">
          <div class="divider-dot">⠿</div>
        </div>

        <div class="content-panel">
          <el-card shadow="never" class="tabs-card">
            <el-tabs v-model="activeTab">
              <!-- 笔记 + 内嵌自测 -->
              <el-tab-pane label="笔记" name="note">
                <!-- 学前诊断（可选功能） -->
                <div v-if="diagnosisEnabled && diagnosis.has_prior" class="diagnosis-card">
                  <div class="diag-head">
                    <span>🧭 学前诊断（先修检测）</span>
                    <el-button v-if="!diagQuestions.length" size="small" @click="loadDiagnosis">重新检测</el-button>
                  </div>
                  <p class="diag-sub">
                    以下 {{ diagQuestions.length }} 题来自本合集前面 {{ diagnosis.prior_notes.length }} 集
                    （{{ diagnosis.prior_notes.map(function (n) { return '第' + n.page + '集' }).join('、') }}），
                    答完即给出「能否跳过先修直接看本集」的建议。
                  </p>
                  <div v-if="diagQuestions.length">
                    <QuizCard
                      v-for="q in diagQuestions"
                      :key="'diag-' + q.note_id + '-' + q.index"
                      :q="q"
                      :index="q.index"
                      :note-id="q.note_id"
                      @jump="jump"
                      @answered="onDiagAnswered"
                    />
                    <div v-if="diagResult" class="diag-result" :class="diagResult.ok ? 'ok' : 'warn'">
                      <b>{{ diagResult.title }}</b><span class="diag-text">{{ diagResult.text }}</span>
                    </div>
                  </div>
                </div>

                <!-- 课程介绍与考点（默认折叠，让目录/知识点直达） -->
                <el-collapse v-model="introOpen" class="intro-collapse">
                  <el-collapse-item name="intro">
                    <template #title>
                      <span class="intro-title">📖 课程介绍与本课考点（{{ introOpen.length ? '收起' : '点击展开' }}）</span>
                    </template>
                    <div v-if="summary" class="summary-box"><LatexText :text="summary" markdown /></div>
                    <div v-if="examPoints.length" class="exam-points">
                      <div class="exam-points-head">🎯 本课考点</div>
                      <div class="exam-points-body">
                        <span v-for="(ep, ei) in examPoints" :key="ei" class="exam-chip">{{ ep }}</span>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>

                <div v-if="!keyframesList.length" class="quiz-entry">
                  <el-button size="small" type="primary" plain :loading="keyframesLoading" @click="generateKeyframes">
                    🖼 提取关键帧截图（嵌入笔记与 Word/PDF 导出）
                  </el-button>
                  <span class="gen-tip">按章节时间戳抽帧，不调用视觉模型</span>
                </div>

                <div v-if="!quizQuestions.length" class="quiz-entry">
                  <el-button size="small" type="primary" :loading="quizGenerating" @click="generateQuiz">
                    ✨ 生成本课自测题（嵌入各章节）
                  </el-button>
                  <span class="gen-tip">单选/判断/填空即时判分，计算题 AI 批改</span>
                </div>

                <div class="note-flex">
                  <!-- 右侧固定竖排目录 + 阅读进度条 -->
                  <aside class="toc-rail">
                    <div class="toc-rail-inner">
                      <div class="toc-rail-title">📑 目录</div>
                      <div v-for="(ch, ci) in chapters" :key="ci" class="toc-chapter">
                        <div class="toc-chapter-head" @click="scrollToChapter(ci)">
                          <span class="toc-no">{{ ci + 1 }}</span>
                          <span class="toc-name">{{ ch.title }}</span>
                        </div>
                        <div
                          v-for="(sec, si) in (ch.sections || [])"
                          :key="si"
                          class="toc-sec"
                          @click="scrollToSection(ci, si)"
                        >
                          <span class="toc-dot" :style="{ background: 'var(--c-badge-' + sec.type + ')' }"></span>
                          <span class="toc-sec-name">{{ sec.heading }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="read-progress" title="阅读进度">
                      <div class="read-progress-fill" :style="{ height: readingProgress + '%' }"></div>
                    </div>
                  </aside>

                  <!-- 正文 -->
                  <div class="note-main">
                    <div v-for="(ch, ci) in chapters" :key="ci" :id="'chapter-' + ci" class="chapter">
                      <h3 class="chapter-title">
                        <span class="chapter-no">{{ ci + 1 }}</span>
                        <span class="chapter-name">{{ ch.title }}</span>
                        <TimeLink v-if="ch.time_stamp" :time="ch.time_stamp" @jump="jump" />
                      </h3>
                      <p v-if="ch.intro" class="chapter-intro">{{ ch.intro }}</p>
                      <div v-if="chapterKeyframes(ci).length" class="chapter-frames">
                        <el-image
                          v-for="(k, ki) in chapterKeyframes(ci)"
                          :key="ki"
                          :src="keyframeUrl(k)"
                          :preview-src-list="chapterKeyframes(ci).map(function (x) { return keyframeUrl(x) })"
                          :initial-index="ki"
                          fit="cover"
                          class="frame-thumb"
                        />
                      </div>

                      <div
                        v-for="(sec, si) in (ch.sections || [])"
                        :key="si"
                        :id="'sec-' + ci + '-' + si"
                        class="note-section"
                        :class="['sec-' + sec.type, { important: sec.important }]"
                      >
                        <div class="sec-head">
                          <span class="sec-badge">{{ sectionTypeLabel(sec.type) }}</span>
                          <span class="sec-heading"><LatexText :text="sec.heading" /></span>
                          <TimeLink v-if="sec.time_stamp" :time="sec.time_stamp" @jump="jump" />
                          <el-tag v-if="sec.important" size="small" type="danger" effect="dark">重点</el-tag>
                          <el-button size="small" text type="warning" @click="openConfusion(ci, si)">
                            🙋 没懂
                          </el-button>
                        </div>
                        <div class="sec-body">
                          <template v-for="(b, bi) in (sec.blocks || [])" :key="bi">
                            <p v-if="b.type === 'text'" class="b-text"><LatexText :text="b.content" markdown /></p>
                            <div v-else-if="b.type === 'formula'" class="b-formula"><LatexText :text="'$$' + b.content + '$$'" /></div>
                            <ol v-else-if="b.type === 'steps'" class="b-steps">
                              <li v-for="(it, k) in b.items" :key="k"><LatexText :text="it" markdown /></li>
                            </ol>
                            <ul v-else-if="b.type === 'list'" class="b-list" :class="{ ordered: b.ordered }">
                              <li v-for="(it, k) in b.items" :key="k"><LatexText :text="it" markdown /></li>
                            </ul>
                            <pre v-else-if="b.type === 'code'" class="b-code"><code>{{ b.content }}</code></pre>
                            <blockquote v-else-if="b.type === 'quote'" class="b-quote"><LatexText :text="b.content" markdown /></blockquote>
                            <table v-else-if="b.type === 'table'" class="b-table">
                              <thead v-if="b.headers && b.headers.length">
                                <tr><th v-for="(h, k) in b.headers" :key="k">{{ h }}</th></tr>
                              </thead>
                              <tbody>
                                <tr v-for="(row, r) in b.rows" :key="r">
                                  <td v-for="(c, k) in row" :key="k"><LatexText :text="c" /></td>
                                </tr>
                              </tbody>
                            </table>
                          </template>
                        </div>
                      </div>

                      <div v-if="ch.key_points && ch.key_points.length" class="chapter-keypoints">
                        <div class="kp-head">✅ 本章要点</div>
                        <ul>
                          <li v-for="(k, ki) in ch.key_points" :key="ki"><LatexText :text="k" markdown /></li>
                        </ul>
                      </div>
                      <div v-if="ch.summary" class="chapter-summary">
                        <span class="cs-label">本章小结：</span><LatexText :text="ch.summary" markdown />
                      </div>

                      <div v-if="chapterQuestions[ci] && chapterQuestions[ci].length" class="chapter-quiz">
                        <div class="chapter-quiz-head">📝 本章自测（{{ chapterQuestions[ci].length }} 题）</div>
                        <QuizCard
                          v-for="q in chapterQuestions[ci]"
                          :key="q.index"
                          :q="q"
                          :index="q.index"
                          :note-id="noteId"
                          :show-variant="variantEnabled"
                          @jump="jump"
                          @answered="loadWrong"
                          @variant="onVariant"
                        />
                      </div>
                    </div>
                    <div v-if="unmatchedQuestions.length" class="chapter-quiz">
                      <div class="chapter-quiz-head">📝 综合自测（{{ unmatchedQuestions.length }} 题）</div>
                      <QuizCard
                        v-for="q in unmatchedQuestions"
                        :key="q.index"
                        :q="q"
                        :index="q.index"
                        :note-id="noteId"
                        :show-variant="variantEnabled"
                        @jump="jump"
                        @answered="loadWrong"
                        @variant="onVariant"
                      />
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <!-- 思维导图 -->
              <el-tab-pane label="思维导图" name="mindmap">
                <MermaidView v-if="mindmap" :code="mindmap" @node-click="jumpBySeconds" />
                <el-empty v-else description="本次生成未输出脑图" />
              </el-tab-pane>

              <!-- 公式板书（数理/计算机专项） -->
              <el-tab-pane label="公式板书" name="formulas">
                <div v-if="!formulasList.length && !formulaItems.length" class="formula-entry">
                  <el-empty description="提取视频关键帧，AI 识别板书/课件公式并转为 LaTeX">
                    <div class="formula-gen">
                      <el-select v-model="visionProvider" size="small" style="width: 220px">
                        <el-option label="DeepSeek Flash（视觉，推荐）" value="deepseek" />
                        <el-option label="通义千问 qwen-vl-max" value="qwen" />
                        <el-option label="Kimi K2（视觉）" value="kimi" />
                      </el-select>
                      <el-button type="primary" size="small" :loading="formulasLoading" @click="generateFormulas">
                        提取板书公式
                      </el-button>
                    </div>
                    <p class="gen-tip">需对应供应商的视觉模型 Key；首次需下载视频流，约 1-3 分钟</p>
                  </el-empty>
                </div>
                <div v-else class="formula-box">
                  <div class="formula-toolbar">
                    <el-button size="small" :loading="formulasLoading" @click="generateFormulas">重新提取</el-button>
                    <span class="gen-tip">识别到 {{ formulasList.length }} 条公式，LaTeX 可直接复制到 Typora/Word/Overleaf</span>
                  </div>
                  <div v-for="(item, ii) in formulaItems" :key="ii" class="formula-frame-block">
                    <div class="formula-frame-head">📺 关键帧 {{ item.frame }}</div>
                    <div class="formula-frame-body">
                      <div class="formula-frame-img">
                        <el-image
                          v-if="formulaImages[item.frame - 1]"
                          :src="formulaImages[item.frame - 1]"
                          fit="contain"
                          :preview-src-list="formulaImages"
                          :initial-index="item.frame - 1"
                          class="frame-img"
                        />
                      </div>
                      <div class="formula-frame-results">
                        <div v-if="!item.formulas.length && !item.notes.length" class="formula-empty-frame">
                          本帧未识别到公式
                        </div>
                        <div v-for="(f, fi) in item.formulas" :key="fi" class="formula-card">
                          <div class="formula-latex"><LatexText :text="f.latex" display /></div>
                          <div v-if="f.description" class="formula-desc"><LatexText :text="f.description" /></div>
                          <el-button size="small" text type="primary" @click="copyLatex(f.latex)">复制 LaTeX</el-button>
                        </div>
                        <div v-for="(n, ni) in item.notes" :key="'n' + ni" class="formula-note-item">
                          <el-tag size="small" type="info" effect="plain">要点</el-tag>
                          <LatexText :text="n" />
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="formulaNotes.length" class="formula-notes">
                    <span class="fn-label">📌 板书要点汇总：</span>
                    <el-tag v-for="(n, ni) in formulaNotes" :key="ni" size="small" effect="plain" class="fn-tag">
                      {{ n }}
                    </el-tag>
                  </div>
                </div>
              </el-tab-pane>

              <!-- 生词（英语专项） -->
              <el-tab-pane v-if="subject === 'english'" label="生词" name="words">
                <div v-if="wordList.length">
                  <el-table :data="wordList" size="small">
                    <el-table-column label="单词" width="130">
                      <template #default="scope"><b>{{ scope.row.word }}</b></template>
                    </el-table-column>
                    <el-table-column label="音标" width="130">
                      <template #default="scope">{{ scope.row.phonetic }}</template>
                    </el-table-column>
                    <el-table-column label="释义" min-width="140">
                      <template #default="scope">{{ scope.row.meaning }}</template>
                    </el-table-column>
                    <el-table-column label="原句" min-width="200">
                      <template #default="scope">{{ scope.row.sentence }}</template>
                    </el-table-column>
                    <el-table-column label="时间" width="120">
                      <template #default="scope">
                        <TimeLink v-if="scope.row.time_stamp" :time="scope.row.time_stamp" @jump="jump" />
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-if="pronList.length" class="pron-box">
                    <h4>语音现象（连读 / 弱读 / 失去爆破）</h4>
                    <div v-for="(p, pi) in pronList" :key="pi" class="pron-item">
                      <el-tag size="small" type="warning">{{ p.phenomenon }}</el-tag>
                      <span class="pron-sentence">{{ p.sentence }}</span>
                      <TimeLink v-if="p.time_stamp" :time="p.time_stamp" @jump="jump" />
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无生词数据" />
              </el-tab-pane>

              <!-- 英语精听听写（可选功能） -->
              <el-tab-pane v-if="subject === 'english' && dictationEnabled" label="听写" name="dictation">
                <div v-if="!dictationItems.length" class="dictation-entry">
                  <el-empty description="精听听写：从原视频字幕挖空，先听后填">
                    <el-button type="primary" :loading="dictationLoading" @click="generateDictation">
                      生成听写练习
                    </el-button>
                  </el-empty>
                  <p class="gen-tip">适用于英语视频（需有官方字幕或本地转写）；AI 选句挖空，重点练核心实词与短语</p>
                </div>
                <div v-else>
                  <div class="dictation-toolbar">
                    <span class="gen-tip">共 {{ dictationItems.length }} 题，点 🔊 跳转原声，先听后填</span>
                    <el-button size="small" :loading="dictationLoading" @click="generateDictation">重新生成</el-button>
                  </div>
                  <DictationCard
                    v-for="(it, i) in dictationItems"
                    :key="i"
                    :item="it"
                    :index="i"
                    :note-id="noteId"
                    @jump="jump"
                    @answered="loadWrong"
                  />
                </div>
              </el-tab-pane>

              <!-- 复盘 -->
              <el-tab-pane label="复盘" name="review">
                <div v-if="wrongList.length" class="wrong-box">
                  <h4>错题本（{{ wrongList.length }}）</h4>
                  <div v-for="(w, wi) in wrongList" :key="w.id || wi" class="wrong-item">
                    <div class="wrong-head">
                      <el-tag size="small" type="danger" effect="plain">{{ qtypeName(w.qtype) }}</el-tag>
                      <el-tag v-if="w.wrong_count > 1" size="small" type="warning" effect="dark">
                        错 {{ w.wrong_count }} 次
                      </el-tag>
                    </div>
                    <div class="wrong-q"><b>题目：</b><LatexText :text="w.question" markdown /></div>
                    <div class="wrong-a"><b>你的答案：</b><LatexText :text="w.user_answer || '（未作答）'" markdown /></div>
                    <div class="wrong-a"><b>正确答案：</b><LatexText :text="w.correct_answer" markdown /></div>
                    <div v-if="w.feedback" class="wrong-feedback">
                      <b>AI 讲解：</b><LatexText :text="w.feedback" markdown />
                    </div>
                    <div v-else-if="w.explanation" class="wrong-feedback">
                      <b>解析：</b><LatexText :text="w.explanation" markdown />
                    </div>
                    <div class="wrong-foot">
                      <TimeLink v-if="w.time_stamp" :time="w.time_stamp" @jump="jump" />
                      <el-button size="small" type="success" plain @click="masterWrong(w)">我已掌握，移除</el-button>
                    </div>
                  </div>
                </div>

                <div v-if="!reviewData">
                  <el-empty description="基于错题生成薄弱点分析与复习计划">
                    <el-button type="primary" :loading="reviewLoading" @click="generateReview">生成复盘分析</el-button>
                  </el-empty>
                </div>
                <div v-else>
                  <el-alert
                    v-if="reviewData.summary"
                    :title="reviewData.summary"
                    type="success"
                    :closable="false"
                    show-icon
                    style="margin-bottom: 12px"
                  />
                  <div v-if="reviewData.weak_points && reviewData.weak_points.length">
                    <h4>薄弱知识点</h4>
                    <div v-for="(w, wi) in reviewData.weak_points" :key="wi" class="weak-item">
                      <div class="weak-head">
                        <span class="weak-point">{{ w.point }}</span>
                        <el-tag
                          :type="w.priority === 'high' ? 'danger' : (w.priority === 'medium' ? 'warning' : 'info')"
                          size="small"
                        >{{ priorityName(w.priority) }}</el-tag>
                      </div>
                      <div v-if="w.reason" class="weak-line"><b>错题表现：</b>{{ w.reason }}</div>
                      <div v-if="w.suggestion" class="weak-line"><b>复习建议：</b>{{ w.suggestion }}</div>
                      <div v-if="w.replay_timestamps && w.replay_timestamps.length" class="weak-line">
                        <b>复习片段：</b>
                        <TimeLink
                          v-for="(t, ti) in w.replay_timestamps"
                          :key="ti"
                          :time="t"
                          @jump="jump"
                        />
                      </div>
                    </div>
                  </div>
                  <el-alert
                    v-else
                    title="暂无错题记录，继续保持！"
                    type="success"
                    :closable="false"
                    show-icon
                    style="margin-bottom: 12px"
                  />
                  <h4 v-if="planList.length">复习计划</h4>
                  <el-table v-if="planList.length" :data="planList" size="small">
                    <el-table-column prop="content" label="复习内容" min-width="160" />
                    <el-table-column prop="due_date" label="复习日期" width="120" />
                    <el-table-column label="状态" width="90">
                      <template #default="scope">
                        <el-checkbox :model-value="scope.row.done" @change="togglePlan(scope.row)">完成</el-checkbox>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </div>
      </div>

      <!-- AI 答疑抽屉 -->
      <el-drawer v-model="chatVisible" title="💬 AI 答疑（基于本笔记）" size="440px">
        <div class="chat-wrap">
          <div class="chat-actions">
            <el-button size="small" text @click="clearChat">清空对话</el-button>
          </div>
          <div ref="chatBody" class="chat-body">
            <div v-if="!chatMessages.length" class="chat-empty">
              <p>针对这份笔记提问，例如：</p>
              <el-tag
                v-for="(s, si) in quickQuestions"
                :key="si"
                class="quick-q"
                effect="plain"
                @click="quickAsk(s)"
              >{{ s }}</el-tag>
            </div>
            <div v-for="(m, i) in chatMessages" :key="i" class="chat-msg" :class="m.role">
              <div class="chat-bubble">
                <template v-if="m.role === 'assistant'">
                  <span v-if="!m.content && !m.error" class="typing">思考中...</span>
                  <template v-else>
                    <div v-if="m.error" class="chat-error">⚠️ {{ m.error }}</div>
                    <template v-for="(part, pi) in parseAssistant(m.content)" :key="pi">
                      <div v-if="part.type === 'text'" class="chat-text" v-html="part.html"></div>
                      <MermaidView v-else :code="part.code" compact />
                    </template>
                    <div v-if="m.content && !(i === chatMessages.length - 1 && chatLoading)" class="msg-tools">
                      <el-button link size="small" @click="copyMessage(m.content)">复制</el-button>
                      <el-button link size="small" @click="retryAsk(i)">重试</el-button>
                    </div>
                  </template>
                </template>
                <template v-else>
                  <span class="user-text">{{ m.content }}</span>
                </template>
              </div>
            </div>
          </div>
          <div class="chat-input">
            <el-input
              v-model="chatInput"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="输入你的问题，Enter 发送，Shift+Enter 换行"
              @keydown="onChatKeydown"
            />
            <el-button v-if="chatLoading" type="danger" plain @click="stopChat">停止</el-button>
            <el-button v-else type="primary" @click="sendChat">发送</el-button>
          </div>
        </div>
      </el-drawer>

      <!-- 没懂：AI 换讲 -->
      <el-dialog v-model="confusionVisible" title="🙋 没懂？换个讲法" width="600px">
        <div class="cf-head">
          <el-tag v-if="confusionSection" size="small" effect="plain">{{ confusionSection }}</el-tag>
          <span v-if="confusionTime" class="cf-time">@ {{ confusionTime }}</span>
        </div>
        <el-input
          v-model="confusionQuestion"
          type="textarea"
          :rows="2"
          placeholder="可选：补充一句卡在哪（比如「这里为什么可以求导」）"
        />
        <div v-if="confusionLoading" class="cf-loading">
          <span class="vp-spinner"></span>
          AI 正在换一种更通俗的讲法…
        </div>
        <div v-else-if="confusionExplanation" class="cf-explanation">
          <LatexText :text="confusionExplanation" markdown />
        </div>
        <template #footer>
          <el-button v-if="confusionExplanation" type="success" @click="resolveConfusion">明白了，移除</el-button>
          <el-button v-else type="primary" :loading="confusionLoading" @click="submitConfusion">
            生成换讲
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import api from '../api'
import { hmsToSeconds, secondsToHms } from '../utils/time'
import { renderMarkdownLite } from '../utils/latex'
import VideoPlayer from '../components/VideoPlayer.vue'
import MermaidView from '../components/MermaidView.vue'
import QuizCard from '../components/QuizCard.vue'
import DictationCard from '../components/DictationCard.vue'
import TimeLink from '../components/TimeLink.vue'
import LatexText from '../components/LatexText.vue'

export default {
  name: 'NoteDetailView',
  components: { VideoPlayer, MermaidView, QuizCard, DictationCard, TimeLink, LatexText },
  data() {
    return {
      noteId: 0,
      loading: false,
      timer: null,
      startedAt: 0,
      tick: 0,
      stageText: '',
      status: 'pending',
      error: '',
      retrying: false,
      bvid: '',
      page: 1,
      title: '',
      subject: 'general',
      summary: '',
      chapters: [],
      examPoints: [],
      mindmap: '',
      activeTab: 'note',
      introOpen: [],
      // 布局
      layoutMode: 'split',
      leftWidth: 52,
      dragging: false,
      readingProgress: 0,
      // 自测
      quizQuestions: [],
      chapterQuestions: [],
      unmatchedQuestions: [],
      quizGenerating: false,
      variantGenerating: false,
      wrongList: [],
      // 功能开关
      dictationEnabled: true,
      variantEnabled: true,
      diagnosisEnabled: true,
      // 英语听写
      dictationItems: [],
      dictationLoading: false,
      // 没懂打点
      confusionVisible: false,
      confusionSection: '',
      confusionTime: '',
      confusionQuestion: '',
      confusionExplanation: '',
      confusionLoading: false,
      confusionPointId: 0,
      lastJumpSec: 0,
      // 学前诊断
      diagnosis: { has_prior: false, prior_notes: [], questions: [] },
      diagQuestions: [],
      diagAnswered: 0,
      diagCorrect: 0,
      // 生词
      wordList: [],
      pronList: [],
      // 公式板书
      formulasList: [],
      formulaItems: [],
      formulaImages: [],
      formulaNotes: [],
      formulasLoading: false,
      visionProvider: 'deepseek',
      // 关键帧
      keyframesList: [],
      keyframesLoading: false,
      // 复盘
      reviewData: null,
      reviewLoading: false,
      planList: [],
      // 答疑
      chatVisible: false,
      chatMessages: [],
      chatInput: '',
      chatLoading: false,
      chatAbort: null,
      chatStorageKey: '',
      jumpedQuery: false,
      quickQuestions: [
        '这段视频主要讲了什么？',
        '帮我总结重点，并划出考点',
        '用更通俗的方式解释第一个知识点'
      ]
    }
  },
  computed: {
    progressPercent() {
      var t = this.elapsedSeconds
      var transcribing = this.stageText.indexOf('转写') >= 0
      if (transcribing) return Math.min(35, 5 + Math.round(t / 2))
      return Math.min(90, 35 + Math.round(t / 3))
    },
    elapsedSeconds() {
      if (this.startedAt) {
        return Math.max(0, Math.floor((Date.now() - this.startedAt) / 1000))
      }
      return this.tick
    },
    hasWords() {
      return this.subject === 'english' && this.wordList.length > 0
    },
    videoPanelStyle() {
      if (this.layoutMode === 'split') return { width: this.leftWidth + '%' }
      return {}
    },
    lastJumpLabel() {
      return secondsToHms(this.lastJumpSec)
    },
    diagResult() {
      if (!this.diagQuestions.length || this.diagAnswered < this.diagQuestions.length) return null
      var ratio = this.diagCorrect / this.diagAnswered
      if (ratio >= 0.7) {
        return { ok: true, title: '✅ 先修已掌握，可以直接开看本集', text: '前面 ' + this.diagnosis.prior_notes.length + ' 集的先修知识点你基本都会了，遇到熟悉的段落可以直接跳过。' }
      }
      return { ok: false, title: '⚠️ 建议先复习再开看', text: '未掌握比例偏高，建议先回到前面几集复习错题（可在复习中心查看），再看本集效果更好。' }
    }
  },
  created() {
    this.noteId = Number(this.$route.params.id)
    this.chatStorageKey = 'bililearn-chat-' + this.noteId
    var saved = localStorage.getItem('bililearn-layout')
    if (saved === 'top' || saved === 'split') this.layoutMode = saved
    var w = parseFloat(localStorage.getItem('bililearn-video-width'))
    if (w >= 30 && w <= 75) this.leftWidth = w
    try {
      var msgs = JSON.parse(localStorage.getItem(this.chatStorageKey) || '[]')
      if (Array.isArray(msgs)) this.chatMessages = msgs
    } catch (e) { /* 忽略损坏的缓存 */ }
    this.loadConfig()
    this.load()
  },
  mounted() {
    this.$nextTick(function () {
      var cp = document.querySelector('.content-panel')
      if (cp) {
        this._cp = cp
        cp.addEventListener('scroll', this.onReadScroll, { passive: true })
        this.onReadScroll()
      }
    })
  },
  beforeUnmount() {
    this.stopPolling()
    this.stopDrag()
    this.stopChat()
    if (this._cp) this._cp.removeEventListener('scroll', this.onReadScroll)
  },
  methods: {
    async loadConfig() {
      try {
        var cfg = await api.get('/config')
        this.dictationEnabled = cfg.dictation_enabled !== false
        this.variantEnabled = cfg.variant_enabled !== false
        this.diagnosisEnabled = cfg.diagnosis_enabled !== false
      } catch (e) { /* 读取失败按默认值 */ }
    },
    async load() {
      this.loading = true
      try {
        var data = await api.get('/notes/' + this.noteId)
        this.applyNote(data)
        if (data.status === 'processing') this.startPolling()
        else this.stopPolling()
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.loading = false
      }
    },
    applyNote(data) {
      this.status = data.status
      this.error = data.error || ''
      if (data.status === 'processing' && data.error) this.stageText = data.error
      if (data.created_at) {
        var iso = String(data.created_at)
        if (iso.indexOf('+') < 0 && !iso.endsWith('Z')) iso += 'Z'
        var ts = new Date(iso).getTime()
        if (!isNaN(ts)) this.startedAt = ts
      }
      this.bvid = data.bvid
      this.page = data.page
      this.title = data.title
      this.subject = data.subject
      this.summary = data.summary
      this.mindmap = data.mindmap
      var note = data.note || {}
      this.chapters = note.chapters || []
      this.examPoints = note.exam_points || []
      this.quizQuestions = ((data.quizzes && data.quizzes.questions) || []).map(function (q, i) {
        return Object.assign({ index: i }, q)
      })
      this.assignQuestions()
      var words = data.words || {}
      this.wordList = words.words || []
      this.pronList = words.pronunciations || []
      var formulas = data.formulas || {}
      this.formulasList = formulas.formulas || []
      this.formulaItems = formulas.items || []
      this.formulaNotes = formulas.notes || []
      if (this.formulaItems.length && !this.formulaImages.length) {
        this.formulaImages = this.formulaItems.map(function (_, i) {
          return '/api/notes/' + this.noteId + '/frames/formulas/frame_' + (i + 1) + '.jpg'
        }.bind(this))
      }
      this.keyframesList = data.keyframes || []
      var dict = data.dictations || {}
      this.dictationItems = dict.items || []
      this.reviewData = (data.review && data.review.weak_points !== undefined) ? data.review : null
      this.planList = (this.reviewData && this.reviewData.plan) ? this.reviewData.plan : []
      if (data.status === 'done') {
        this.loadWrong()
        if (this.diagnosisEnabled) this.loadDiagnosis()
        if (!this.jumpedQuery) {
          this.jumpedQuery = true
          var t = parseFloat(this.$route.query.t)
          if (t > 0) this.jumpBySeconds(t)
        }
      }
    },
    assignQuestions() {
      var self = this
      this.chapterQuestions = this.chapters.map(function () { return [] })
      this.unmatchedQuestions = []
      // v2 结构按章首时间戳划定区间：章 i 覆盖 [章首, 下一章首)
      var starts = this.chapters.map(function (ch) {
        return hmsToSeconds(ch && ch.time_stamp)
      })
      var ends = starts.map(function (s, i) {
        if (!(s > 0)) return null
        var later = starts.slice(i + 1).filter(function (t) { return t > s })
        return later.length ? later[0] : Infinity
      })
      this.quizQuestions.forEach(function (q) {
        if (!q.time_stamp) { self.unmatchedQuestions.push(q); return }
        var sec = hmsToSeconds(q.time_stamp)
        var best = -1
        for (var i = 0; i < self.chapters.length; i++) {
          if (starts[i] > 0 && sec >= starts[i] && sec < ends[i]) { best = i; break }
        }
        if (best < 0) {
          var bestDist = Infinity
          for (var j = 0; j < self.chapters.length; j++) {
            if (!(starts[j] > 0)) continue
            var d = Math.abs(sec - starts[j])
            if (d < bestDist) { bestDist = d; best = j }
          }
        }
        if (best >= 0) self.chapterQuestions[best].push(q)
        else self.unmatchedQuestions.push(q)
      })
    },
    sectionTypeLabel(type) {
      var names = {
        definition: '定义',
        concept: '讲解',
        derivation: '推导',
        example: '例题',
        code: '代码',
        comparison: '对比',
        conclusion: '结论',
        keypoints: '要点'
      }
      return names[type] || '知识点'
    },
    scrollToChapter(ci) {
      var el = document.getElementById('chapter-' + ci)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    scrollToSection(ci, si) {
      var el = document.getElementById('sec-' + ci + '-' + si)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    onReadScroll() {
      var cp = this._cp
      if (!cp) return
      var max = cp.scrollHeight - cp.clientHeight
      this.readingProgress = max > 0 ? Math.min(100, Math.round(cp.scrollTop / max * 100)) : 0
    },
    startPolling() {
      if (this.timer) return
      this.timer = setInterval(this.poll, 3000)
    },
    stopPolling() {
      if (this.timer) {
        clearInterval(this.timer)
        this.timer = null
      }
    },
    async poll() {
      try {
        var st = await api.get('/notes/' + this.noteId + '/status')
        if (st.status === 'done') {
          this.stopPolling()
          await this.load()
        } else if (st.status === 'failed') {
          this.stopPolling()
          this.status = 'failed'
          this.error = st.error || ''
        } else {
          this.tick += 3
          if (st.error) this.stageText = st.error
        }
      } catch (e) {
        /* 忽略轮询错误 */
      }
    },
    async loadWrong() {
      try {
        this.wrongList = await api.get('/quiz/' + this.noteId + '/wrong')
      } catch (e) {
        this.wrongList = []
      }
    },
    async masterWrong(w) {
      try {
        await api.post('/quiz/wrong/' + w.id + '/master')
        this.wrongList = this.wrongList.filter(function (x) { return x.id !== w.id })
        ElMessage.success('已标记掌握')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    qtypeName(t) {
      var names = { single: '单选题', judge: '判断题', fill: '填空题', calc: '计算题', proof: '思考卡' }
      return names[t] || '题目'
    },
    jump(hms) {
      var sec = hmsToSeconds(hms)
      this.lastJumpSec = sec
      if (this.$refs.player) this.$refs.player.jumpTo(sec)
    },
    jumpBySeconds(sec) {
      this.lastJumpSec = sec
      if (this.$refs.player) this.$refs.player.jumpTo(sec)
    },
    async download(type) {
      var url = '/api/export/' + this.noteId + '/' + type
      try {
        var resp = await fetch(url)
        if (!resp.ok) {
          var detail = '导出失败（HTTP ' + resp.status + '）'
          try {
            var err = await resp.json()
            if (err && err.detail) detail = err.detail
          } catch (e) { /* 非 JSON 错误体 */ }
          ElMessage.error(detail)
          return
        }
        var blob = await resp.blob()
        var disposition = resp.headers.get('Content-Disposition') || ''
        var nameMatch = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^;"']+)/i)
        var filename = nameMatch ? decodeURIComponent(nameMatch[1]) : ('note-' + this.noteId + '.' + type.replace('anki.csv', 'csv'))
        var link = document.createElement('a')
        link.href = URL.createObjectURL(blob)
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setTimeout(function () { URL.revokeObjectURL(link.href) }, 1000)
      } catch (e) {
        ElMessage.error('导出失败：' + (e.message || e))
      }
    },
    async retryGenerate() {
      if (!this.bvid) return
      this.retrying = true
      try {
        var res = await api.post('/notes/generate', {
          bvid: this.bvid,
          page: this.page || 1,
          subject: this.subject || 'general',
          title: this.title || ''
        })
        this.$router.replace('/note/' + res.id)
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.retrying = false
      }
    },
    async deleteNote() {
      try {
        await api.delete('/notes/' + this.noteId)
        ElMessage.success('已删除')
        this.$router.push('/history')
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    async generateQuiz() {
      this.quizGenerating = true
      try {
        var res = await api.post('/quiz/generate', { note_id: this.noteId })
        this.quizQuestions = (res.questions || []).map(function (q, i) {
          return Object.assign({ index: i }, q)
        })
        this.assignQuestions()
        ElMessage.success('已生成 ' + this.quizQuestions.length + ' 道自测题，嵌入各章节下方')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.quizGenerating = false
      }
    },
    async onVariant(q) {
      if (this.variantGenerating) return
      this.variantGenerating = true
      try {
        var res = await api.post('/quiz/variant', { note_id: this.noteId, question: q })
        var item = Object.assign({ index: this.quizQuestions.length, is_variant: true }, res)
        this.quizQuestions.push(item)
        this.assignQuestions()
        ElMessage.success('已生成变式题（AI 换数字/换情境，考察同一知识点）')
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.variantGenerating = false
      }
    },
    chapterKeyframes(ci) {
      return this.keyframesList.filter(function (k) { return k.chapter === ci })
    },
    keyframeUrl(k) {
      var img = k.image || ''
      // 旧版笔记存的是相对目录路径（{id}_frames/xxx.jpg），新版只存文件名
      if (img.indexOf('/') >= 0 || img.indexOf('\\') >= 0) {
        return '/api/notes/' + this.noteId + '/frames/' + img
      }
      return '/api/notes/' + this.noteId + '/frames/keyframes/' + img
    },
    async generateKeyframes() {
      this.keyframesLoading = true
      try {
        var res = await api.post('/notes/' + this.noteId + '/keyframes')
        this.keyframesList = res.keyframes || []
        ElMessage.success('已提取 ' + this.keyframesList.length + ' 张关键帧')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.keyframesLoading = false
      }
    },
    async generateFormulas() {
      this.formulasLoading = true
      try {
        var res = await api.post('/notes/' + this.noteId + '/formulas', { provider: this.visionProvider })
        this.formulasList = res.formulas || []
        this.formulaItems = res.items || this.formulaItems || []
        this.formulaImages = res.images || []
        this.formulaNotes = res.notes || []
        if (this.formulasList.length) ElMessage.success('已识别 ' + this.formulasList.length + ' 条公式')
        else ElMessage.warning('关键帧中未识别到公式（该视频可能以动画/口述为主）')
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.formulasLoading = false
      }
    },
    async copyLatex(text) {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success('LaTeX 已复制')
      } catch (e) {
        ElMessage.error('复制失败')
      }
    },
    async generateReview() {
      this.reviewLoading = true
      try {
        var res = await api.post('/review/analyze', { note_id: this.noteId })
        this.reviewData = res
        this.planList = res.plan || []
        ElMessage.success('复盘分析完成')
      } catch (e) {
        ElMessage.error(e.message)
      } finally {
        this.reviewLoading = false
      }
    },
    async togglePlan(row) {
      try {
        var res = await api.post('/review/plan/' + row.id + '/toggle')
        row.done = res.done
      } catch (e) {
        ElMessage.error(e.message)
      }
    },
    priorityName(p) {
      var names = { high: '高优先级', medium: '中优先级', low: '低优先级' }
      return names[p] || p
    },
    // 英语听写
    async generateDictation() {
      this.dictationLoading = true
      try {
        var res = await api.post('/notes/' + this.noteId + '/dictation')
        this.dictationItems = res.items || []
        if (this.dictationItems.length) ElMessage.success('已生成 ' + this.dictationItems.length + ' 道听写题')
        else ElMessage.warning('未生成听写题，可重试')
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.dictationLoading = false
      }
    },
    // 没懂打点
    openConfusion(ci, si) {
      var ch = this.chapters[ci]
      var sec = ch && ch.sections ? ch.sections[si] : null
      this.confusionSection = sec ? sec.heading : (ch ? ch.title : '')
      this.confusionTime = sec && sec.time_stamp ? sec.time_stamp : (ch && ch.time_stamp ? ch.time_stamp : '')
      this.openConfusionDialog()
    },
    openConfusionAtTime() {
      this.confusionSection = ''
      this.confusionTime = this.lastJumpLabel
      this.openConfusionDialog()
    },
    openConfusionDialog() {
      this.confusionVisible = true
      this.confusionQuestion = ''
      this.confusionExplanation = ''
      this.confusionLoading = false
      this.confusionPointId = 0
    },
    async submitConfusion() {
      this.confusionLoading = true
      try {
        var created = await api.post('/notes/' + this.noteId + '/confusions', {
          time_stamp: this.confusionTime === this.lastJumpLabel ? secondsToHms(this.lastJumpSec) : this.confusionTime,
          section: this.confusionSection,
          question: this.confusionQuestion
        })
        this.confusionPointId = created.id
        var res = await api.post('/notes/' + this.noteId + '/confusions/' + created.id + '/explain')
        this.confusionExplanation = res.explanation
        ElMessage.success('已打点并生成换讲')
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || e.message)
      } finally {
        this.confusionLoading = false
      }
    },
    async resolveConfusion() {
      if (!this.confusionPointId) { this.confusionVisible = false; return }
      try {
        await api.post('/notes/' + this.noteId + '/confusions/' + this.confusionPointId + '/resolve')
        ElMessage.success('已解决，加油！')
      } catch (e) { /* 忽略 */ }
      this.confusionVisible = false
    },
    // 学前诊断
    async loadDiagnosis() {
      try {
        var res = await api.get('/notes/' + this.noteId + '/diagnosis')
        this.diagnosis = res
        this.diagQuestions = (res.questions || []).map(function (q, i) {
          return Object.assign({ index: i }, q)
        })
        this.diagAnswered = 0
        this.diagCorrect = 0
      } catch (e) {
        this.diagnosis = { has_prior: false, prior_notes: [], questions: [] }
      }
    },
    onDiagAnswered(payload) {
      if (this.diagAnswered >= this.diagQuestions.length) return
      this.diagAnswered++
      if (payload && payload.correct) this.diagCorrect++
    },
    // 拖拽分栏
    startDrag(e) {
      e.preventDefault()
      this.dragging = true
      try { e.currentTarget.setPointerCapture(e.pointerId) } catch (_) {}
      window.addEventListener('pointermove', this.onDrag)
      window.addEventListener('pointerup', this.stopDrag)
      window.addEventListener('pointercancel', this.stopDrag)
    },
    onDrag(e) {
      if (!this.dragging) return
      var el = this.$refs.splitLayout
      if (!el) return
      var rect = el.getBoundingClientRect()
      var pct = ((e.clientX - rect.left) / rect.width) * 100
      this.leftWidth = Math.min(75, Math.max(30, Math.round(pct)))
    },
    stopDrag(e) {
      if (!this.dragging) return
      this.dragging = false
      window.removeEventListener('pointermove', this.onDrag)
      window.removeEventListener('pointerup', this.stopDrag)
      window.removeEventListener('pointercancel', this.stopDrag)
      try { e && e.currentTarget && e.currentTarget.releasePointerCapture && e.currentTarget.releasePointerCapture(e.pointerId) } catch (_) {}
      localStorage.setItem('bililearn-video-width', String(this.leftWidth))
      localStorage.setItem('bililearn-layout', this.layoutMode)
    },
    // AI 答疑
    onChatKeydown(e) {
      // 中文输入法组词期间（isComposing / keyCode 229）不触发发送
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
        e.preventDefault()
        this.sendChat()
      }
    },
    persistChat() {
      try {
        var clean = this.chatMessages.map(function (m) {
          return { role: m.role, content: m.content || '', error: m.error || '' }
        })
        localStorage.setItem(this.chatStorageKey, JSON.stringify(clean.slice(-40)))
      } catch (e) { /* 存储满或不可用时忽略 */ }
    },
    async sendChat(question) {
      var msg = (question !== undefined ? String(question) : (this.chatInput || '')).trim()
      if (!msg || this.chatLoading) return
      this.chatInput = ''
      this.chatMessages.push({ role: 'user', content: msg })
      var assistantMsg = { role: 'assistant', content: '', error: '' }
      this.chatMessages.push(assistantMsg)
      this.chatLoading = true
      this.persistChat()
      this.scrollChatBottom()
      var history = this.chatMessages.slice(-11, -1).map(function (m) {
        return { role: m.role, content: m.content }
      })
      var controller = new AbortController()
      this.chatAbort = controller
      try {
        var resp = await fetch('/api/notes/' + this.noteId + '/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg, history: history }),
          signal: controller.signal
        })
        if (!resp.ok) {
          var detail = 'HTTP ' + resp.status
          try {
            var errBody = await resp.json()
            if (errBody && errBody.detail) detail = errBody.detail
          } catch (e) { /* 非 JSON 错误体 */ }
          throw new Error(detail)
        }
        var reader = resp.body.getReader()
        var decoder = new TextDecoder('utf-8')
        var buffer = ''
        while (true) {
          var chunk = await reader.read()
          if (chunk.done) break
          buffer += decoder.decode(chunk.value, { stream: true })
          var parts = buffer.split('\n\n')
          buffer = parts.pop()
          for (var i = 0; i < parts.length; i++) {
            var line = parts[i].trim()
            if (!line || line.indexOf('data:') !== 0) continue
            var payload = null
            try { payload = JSON.parse(line.slice(5).trim()) } catch (e) { continue }
            // 错误作为独立提示，不覆盖已生成的内容
            if (payload.error) assistantMsg.error = payload.error
            else if (payload.delta) assistantMsg.content += payload.delta
            this.scrollChatBottom()
          }
        }
      } catch (e) {
        if (e.name === 'AbortError') {
          if (!assistantMsg.content) assistantMsg.error = '已停止生成'
        } else {
          assistantMsg.error = '请求失败：' + (e.message || e)
        }
      } finally {
        this.chatLoading = false
        this.chatAbort = null
        this.persistChat()
        this.scrollChatBottom()
      }
    },
    stopChat() {
      if (this.chatAbort) this.chatAbort.abort()
    },
    async copyMessage(text) {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success('已复制')
      } catch (e) {
        ElMessage.error('复制失败')
      }
    },
    retryAsk(index) {
      if (this.chatLoading) return
      var userMsg = this.chatMessages[index - 1]
      if (!userMsg || userMsg.role !== 'user') return
      var q = userMsg.content
      this.chatMessages.splice(index - 1, 2)
      this.sendChat(q)
    },
    quickAsk(text) {
      this.sendChat(text)
    },
    parseAssistant(content) {
      // 兼容 ``` 后空格 / \r\n / 大写 Mermaid；未闭合围栏（流式中）保留为文本
      var regex = /```[ \t]*mermaid[ \t]*\r?\n([\s\S]*?)```/gi
      var parts = []
      var last = 0
      var m
      while ((m = regex.exec(content))) {
        if (m.index > last) parts.push({ type: 'text', html: renderMarkdownLite(content.slice(last, m.index)) })
        parts.push({ type: 'mermaid', code: m[1].trim() })
        last = m.index + m[0].length
      }
      if (last < content.length) parts.push({ type: 'text', html: renderMarkdownLite(content.slice(last)) })
      if (!parts.length) parts.push({ type: 'text', html: renderMarkdownLite(content) })
      return parts
    },
    clearChat() {
      this.chatMessages = []
      this.chatInput = ''
      try { localStorage.removeItem(this.chatStorageKey) } catch (e) { /* 忽略 */ }
    },
    scrollChatBottom() {
      var self = this
      this.$nextTick(function () {
        if (self.$refs.chatBody) self.$refs.chatBody.scrollTop = self.$refs.chatBody.scrollHeight
      })
    }
  },
  watch: {
    layoutMode(val) {
      localStorage.setItem('bililearn-layout', val)
    }
  }
}
</script>

<style scoped>
.status-box { max-width: 560px; margin: 60px auto; }
.stage-text { color: var(--c-primary); font-weight: 600; }
.stage-tip { color: var(--c-text-3); font-size: 13px; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
  margin-bottom: 12px; background: var(--c-bg-elev); border: 1px solid var(--c-border); border-radius: 10px; padding: 8px 14px;
}
.toolbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.drag-tip { color: var(--c-text-3); font-size: 12px; }

/* 布局：分栏模式下笔记面板独立滚动，视频面板固定不动 */
.layout.split {
  display: flex; align-items: stretch;
  height: calc(100vh - 162px); overflow: hidden;
}
.layout.top { display: block; }
.layout.dragging { user-select: none; }
.video-panel { min-width: 0; }
.layout.split .video-panel {
  flex-shrink: 0; padding-right: 10px;
  align-self: flex-start; overflow-y: auto;
}
.layout.top .video-panel {
  position: sticky; top: 0; z-index: 20; background: var(--c-bg);
  padding: 8px 0 4px; margin-bottom: 12px;
}
.layout.top .sticky-video { max-width: 900px; margin: 0 auto; }
.meta-line { margin: 10px 0 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.note-title { font-size: 15px; font-weight: 600; color: var(--c-text); }

.split-divider {
  flex-shrink: 0; width: 16px; cursor: col-resize;
  display: flex; align-items: center; justify-content: center;
  position: relative; color: var(--c-text-3); user-select: none; align-self: stretch;
}
.split-divider::before {
  content: ''; position: absolute; left: 7px; top: 0; bottom: 0;
  width: 2px; background: var(--c-border); border-radius: 2px;
  transition: background .15s;
}
.split-divider:hover::before,
.layout.dragging .split-divider::before { background: var(--c-primary); }
.divider-dot {
  position: relative; z-index: 1;
  width: 22px; height: 28px; border-radius: 8px;
  background: var(--c-bg-elev); border: 1px solid var(--c-border);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--c-text-3); cursor: col-resize;
  box-shadow: 0 1px 4px rgba(0, 0, 0, .1); transition: all .15s;
}
.layout.dragging .divider-dot,
.split-divider:hover .divider-dot { border-color: var(--c-primary); color: var(--c-primary); }

.content-panel { flex: 1; min-width: 0; }
.layout.split .content-panel { height: 100%; overflow-y: auto; padding: 2px 6px 24px 2px; }
.content-panel::-webkit-scrollbar { width: 8px; }
.content-panel::-webkit-scrollbar-thumb { background: var(--c-border); border-radius: 4px; }
.content-panel::-webkit-scrollbar-thumb:hover { background: var(--c-text-3); }
html.dark .content-panel::-webkit-scrollbar-thumb { background: var(--c-border); }
.tabs-card { border-radius: 10px; }

/* 学前诊断 */
.diagnosis-card {
  border: 1px solid var(--c-primary-border); background: var(--c-primary-soft);
  border-radius: 10px; padding: 12px 14px; margin-bottom: 14px;
}
.diag-head { display: flex; align-items: center; justify-content: space-between; font-size: 14px; font-weight: 700; color: var(--c-primary-active); margin-bottom: 4px; }
html.dark .diag-head { color: var(--c-primary); }
.diag-sub { font-size: 12.5px; color: var(--c-text-2); line-height: 1.7; margin: 0 0 10px; }
.diag-result { margin-top: 10px; padding: 10px 14px; border-radius: 8px; font-size: 13px; line-height: 1.8; display: flex; gap: 8px; flex-wrap: wrap; }
.diag-result.ok { background: var(--c-success-soft); border: 1px solid var(--c-success); color: var(--c-text); }
.diag-result.warn { background: var(--c-accent-soft); border: 1px solid var(--c-accent-border); color: var(--c-text); }
.diag-text { color: var(--c-text-2); }

/* 介绍与考点折叠 */
.intro-collapse { margin-bottom: 14px; border-radius: 10px; border: 1px solid var(--c-border-light); background: var(--c-bg-elev); }
.intro-collapse :deep(.el-collapse-item__header) { background: transparent; color: var(--c-text); font-size: 14px; padding: 0 6px; }
.intro-collapse :deep(.el-collapse-item__wrap) { background: transparent; border-bottom: none; }
.intro-title { color: var(--c-text-2); font-weight: 600; }

/* 笔记 */
.summary-box {
  background: var(--c-primary-soft); border-left: 4px solid var(--c-primary);
  padding: 12px 16px; border-radius: 8px; margin-bottom: 14px; color: var(--c-text);
  line-height: 1.8;
}
.exam-points {
  border: 1px solid var(--c-accent-border); background: var(--c-accent-soft);
  border-radius: 10px; padding: 12px 14px; margin-bottom: 14px;
}
.exam-points-head { font-size: 13px; font-weight: 700; color: var(--c-accent); margin-bottom: 8px; }
.exam-points-body { display: flex; flex-wrap: wrap; gap: 8px; }
.exam-chip {
  font-size: 12.5px; color: var(--c-accent); background: var(--c-bg-elev);
  border: 1px solid var(--c-accent-border); border-radius: 999px; padding: 3px 12px; line-height: 1.6;
}

/* 笔记：横向吸顶目录 + 正文占满 */
.note-flex { display: block; }
.note-main, .diagnosis-card, .intro-collapse, .quiz-entry { margin-left: 0; }
/* 右侧固定竖排目录 + 阅读进度条 */
.toc-rail {
  position: fixed; right: 14px; top: 200px; z-index: 30;
  display: flex; align-items: stretch; gap: 8px;
}
.toc-rail-inner {
  width: 176px; max-height: calc(100vh - 240px); overflow-y: auto;
  border: 1px solid var(--c-border-light); border-radius: 10px;
  background: var(--c-bg-elev); padding: 10px 8px;
  scrollbar-width: thin;
}
.toc-rail-title { font-size: 13px; font-weight: 700; color: var(--c-text); padding: 0 6px 8px; border-bottom: 1px dashed var(--c-border); margin-bottom: 6px; }
.toc-chapter { margin-bottom: 2px; }
.toc-chapter-head {
  display: flex; align-items: center; gap: 6px; padding: 5px 6px; border-radius: 6px;
  cursor: pointer; font-size: 13px; font-weight: 600; color: var(--c-text);
  transition: background .12s;
}
.toc-chapter-head:hover { background: var(--c-bg-soft); color: var(--c-primary); }
.toc-no {
  flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center;
  min-width: 17px; height: 17px; padding: 0 4px; border-radius: 4px;
  background: var(--c-primary); color: #fff; font-size: 11px; font-weight: 700;
}
html.dark .toc-no { color: #08231f; }
.toc-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toc-sec {
  display: flex; align-items: center; gap: 6px; padding: 3px 6px 3px 12px; border-radius: 5px;
  cursor: pointer; font-size: 12.5px; color: var(--c-text-2); transition: background .12s;
}
.toc-sec:hover { background: var(--c-bg-soft); color: var(--c-primary); }
.toc-dot { flex-shrink: 0; width: 6px; height: 6px; border-radius: 50%; }
.toc-sec-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.read-progress {
  width: 5px; border-radius: 3px; background: var(--c-border);
  position: relative; overflow: hidden; min-height: 280px;
}
.read-progress-fill {
  position: absolute; left: 0; top: 0; width: 100%;
  background: var(--c-primary); transition: height .12s ease-out;
}

.chapter { margin-bottom: 26px; }
.chapter-title {
  margin: 14px 0 6px; font-size: 17px; font-weight: 700; color: var(--c-text);
  border-left: 4px solid var(--c-primary); padding: 2px 0 2px 10px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.chapter-no {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 6px; border-radius: 6px;
  background: var(--c-primary); color: #fff; font-size: 12px; font-weight: 700;
}
.chapter-name { flex: 1; min-width: 0; }
.chapter-intro {
  margin: 6px 0 10px; color: var(--c-text-2); font-size: 14px; line-height: 1.8;
  padding-left: 14px; border-left: 2px solid var(--c-border);
}

/* 小节（教材精编卡片）：分隔强化 */
.note-section {
  border: 1px solid var(--c-border-light); border-radius: 12px;
  background: var(--c-bg-elev); padding: 14px 18px;
  margin: 16px 0; box-shadow: var(--c-shadow-card);
}
.note-section.important { border-color: var(--c-accent-border); background: var(--c-accent-soft); }
.sec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.sec-badge {
  flex-shrink: 0; font-size: 12px; font-weight: 700; line-height: 1;
  padding: 4px 9px; border-radius: 6px; border: 1px solid;
}
.sec-heading { font-size: 15px; font-weight: 700; color: var(--c-text); flex: 1; min-width: 0; }
.sec-body {
  font-size: 14px; line-height: 1.85; color: var(--c-text);
  border-top: 1px dashed var(--c-border-light); padding-top: 10px; margin-top: 6px;
}
.sec-body :deep(.katex-display) { margin: 6px 0; }
.b-text { margin: 8px 0; }
.b-formula {
  margin: 12px 0; padding: 12px 14px; background: var(--c-bg-soft);
  border-radius: 8px; overflow-x: auto; text-align: center;
}
.b-steps { margin: 8px 0; padding-left: 0; list-style: none; counter-reset: step; }
.b-steps li {
  position: relative; padding: 5px 0 5px 34px; margin: 5px 0; counter-increment: step;
}
.b-steps li::before {
  content: counter(step); position: absolute; left: 0; top: 7px;
  width: 21px; height: 21px; border-radius: 50%; background: var(--c-primary);
  color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.b-list { margin: 8px 0; padding-left: 22px; }
.b-list.ordered { list-style: decimal; }
.b-list li { margin: 3px 0; }
.b-code {
  background: var(--c-code-bg); color: var(--c-code-text); border-radius: 8px;
  padding: 12px 14px; overflow-x: auto; margin: 10px 0; font-size: 13px; line-height: 1.6;
  font-family: Consolas, Monaco, 'Courier New', monospace;
}
.b-quote {
  margin: 10px 0; padding: 8px 14px; border-left: 3px solid var(--c-text-3);
  color: var(--c-text-2); background: var(--c-bg-soft); border-radius: 0 8px 8px 0;
}
.b-table {
  border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13.5px;
  display: block; overflow-x: auto;
}
.b-table th, .b-table td { border: 1px solid var(--c-border); padding: 7px 12px; text-align: left; }
.b-table th { background: var(--c-primary-soft); color: var(--c-primary-active); font-weight: 700; white-space: nowrap; }
.b-table tr:nth-child(even) td { background: var(--c-bg-soft); }
html.dark .b-table th { color: var(--c-primary); }

/* 小节类型徽标配色 */
.sec-definition .sec-badge { color: var(--c-badge-definition); background: var(--c-badge-definition-soft); border-color: var(--c-badge-definition-border); }
.sec-concept .sec-badge { color: var(--c-badge-concept); background: var(--c-badge-concept-soft); border-color: var(--c-badge-concept-border); }
.sec-derivation .sec-badge { color: var(--c-badge-derivation); background: var(--c-badge-derivation-soft); border-color: var(--c-badge-derivation-border); }
.sec-example .sec-badge { color: var(--c-badge-example); background: var(--c-badge-example-soft); border-color: var(--c-badge-example-border); }
.sec-code .sec-badge { color: var(--c-badge-code); background: var(--c-badge-code-soft); border-color: var(--c-badge-code-border); }
.sec-comparison .sec-badge { color: var(--c-badge-comparison); background: var(--c-badge-comparison-soft); border-color: var(--c-badge-comparison-border); }
.sec-conclusion .sec-badge { color: var(--c-badge-conclusion); background: var(--c-badge-conclusion-soft); border-color: var(--c-badge-conclusion-border); }
.sec-keypoints .sec-badge { color: var(--c-badge-keypoints); background: var(--c-badge-keypoints-soft); border-color: var(--c-badge-keypoints-border); }
.sec-definition { border-left: 3px solid var(--c-badge-definition-border); }
.sec-concept { border-left: 3px solid var(--c-badge-concept-border); }
.sec-derivation { border-left: 3px solid var(--c-badge-derivation-border); }
.sec-example { border-left: 3px solid var(--c-badge-example-border); }
.sec-code { border-left: 3px solid var(--c-badge-code-border); }
.sec-comparison { border-left: 3px solid var(--c-badge-comparison-border); }
.sec-conclusion { border-left: 3px solid var(--c-badge-conclusion-border); }
.sec-keypoints { border-left: 3px solid var(--c-badge-keypoints-border); }

/* 章末要点与小结 */
.chapter-keypoints {
  margin: 12px 0; padding: 10px 14px; border-radius: 10px;
  background: var(--c-badge-keypoints-soft); border: 1px solid var(--c-badge-keypoints-border);
}
.kp-head { font-size: 13px; font-weight: 700; color: var(--c-badge-keypoints); margin-bottom: 4px; }
.chapter-keypoints ul { margin: 4px 0; padding-left: 22px; }
.chapter-keypoints li { margin: 3px 0; font-size: 14px; line-height: 1.8; }
.chapter-summary {
  margin: 12px 0; padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.8;
  background: var(--c-success-soft); color: var(--c-text);
}
.cs-label { font-weight: 700; color: var(--c-success); }

.quiz-entry { margin-bottom: 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.chapter-quiz { margin: 12px 0 6px; }
.chapter-quiz-head {
  font-size: 13px; font-weight: 600; color: var(--c-primary);
  background: var(--c-primary-soft); border-radius: 6px; padding: 6px 10px; margin-bottom: 10px;
}

/* 关键帧 */
.chapter-frames { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 10px; }
.frame-thumb { width: 150px; height: 90px; border-radius: 8px; border: 1px solid var(--c-border); cursor: pointer; }
.typing { color: var(--c-text-3); }

/* 公式板书 */
.formula-entry { padding: 8px 0; }
.formula-gen { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.formula-toolbar { margin-bottom: 14px; display: flex; align-items: center; flex-wrap: wrap; }
.formula-frame-block { margin-bottom: 18px; border: 1px solid var(--c-border); border-radius: 10px; overflow: hidden; }
.formula-frame-head {
  background: var(--c-primary-soft); color: var(--c-primary); font-size: 13px; font-weight: 600;
  padding: 6px 12px; border-bottom: 1px solid var(--c-primary-border);
}
.formula-frame-body { display: flex; gap: 14px; padding: 12px; flex-wrap: wrap; }
.formula-frame-img { flex: 0 0 300px; max-width: 100%; }
.formula-frame-img .frame-img { width: 100%; max-height: 240px; background: #000; border-radius: 6px; cursor: zoom-in; }
.formula-frame-results { flex: 1; min-width: 240px; }
.formula-empty-frame { color: var(--c-text-3); font-size: 13px; padding: 8px 0; }
.formula-note-item { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; line-height: 1.8; margin: 6px 0; }
.formula-card {
  background: var(--c-bg-soft); border: 1px solid var(--c-border); border-left: 3px solid var(--c-primary);
  border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;
}
.formula-latex {
  font-family: 'Cambria Math', 'Times New Roman', serif;
  font-size: 15px; color: var(--c-text); overflow-x: auto; white-space: pre-wrap;
  word-break: break-all; margin-bottom: 6px;
}
.formula-desc { font-size: 13px; color: var(--c-text-2); line-height: 1.7; }
.formula-notes { margin: 10px 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.fn-label { font-size: 13px; color: var(--c-text-2); }
.fn-tag { cursor: default; }

/* 生词 */
.pron-box { margin-top: 20px; }
.pron-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px dashed var(--c-border); flex-wrap: wrap; }
.pron-sentence { color: var(--c-text-2); flex: 1; min-width: 200px; }

/* 听写 */
.dictation-entry { padding: 8px 0; }
.dictation-toolbar { margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }

/* 复盘 */
.wrong-box { margin-bottom: 20px; }
.wrong-item {
  border-left: 3px solid var(--c-danger); background: var(--c-danger-soft); padding: 10px 12px;
  margin-bottom: 10px; border-radius: 4px; font-size: 13px; line-height: 1.8;
}
.wrong-feedback { margin-top: 4px; color: var(--c-text); }
.wrong-head { display: flex; gap: 6px; margin-bottom: 6px; }
.wrong-q, .wrong-a { margin: 3px 0; }
.wrong-foot { display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.weak-item { border: 1px solid var(--c-border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.weak-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.weak-point { font-weight: 600; }
.weak-line { font-size: 13px; line-height: 1.8; color: var(--c-text-2); }
h4 { margin: 16px 0 8px; }

/* 答疑抽屉 */
:deep(.el-drawer__body) { height: 100%; padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.chat-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 2px 16px 14px; }
.chat-actions { display: flex; justify-content: flex-end; margin-bottom: 4px; flex-shrink: 0; }
.chat-body { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 4px; }
.chat-empty { color: var(--c-text-3); font-size: 13px; line-height: 2; padding: 12px; }
.quick-q { cursor: pointer; margin: 4px 6px 4px 0; }
.chat-msg { display: flex; margin-bottom: 10px; }
.chat-msg.user { justify-content: flex-end; }
.chat-bubble {
  max-width: 86%; min-width: 0; padding: 9px 12px; border-radius: 10px; font-size: 13px; line-height: 1.7;
  word-break: break-word; overflow-x: auto;
}
.chat-msg.user .chat-bubble { background: var(--c-primary); color: #fff; border-bottom-right-radius: 2px; }
.chat-msg.assistant .chat-bubble { background: var(--c-bg-soft); color: var(--c-text); border-bottom-left-radius: 2px; }
.chat-bubble.typing { color: var(--c-text-3); }
.user-text { white-space: pre-wrap; }
.chat-text { line-height: 1.7; }
.chat-error {
  color: var(--c-danger); background: var(--c-danger-soft); border-radius: 4px;
  padding: 4px 8px; margin-bottom: 6px; font-size: 12px;
}
.msg-tools { display: flex; gap: 4px; margin-top: 4px; justify-content: flex-end; }
.msg-tools :deep(.el-button) { font-size: 12px; padding: 0; height: auto; }
.chat-bubble .mermaid-view { margin: 6px 0; }
.chat-input { display: flex; gap: 8px; align-items: flex-end; padding-top: 10px; border-top: 1px solid var(--c-border); flex-shrink: 0; }
.chat-input .el-textarea { flex: 1; }

/* 没懂换讲 */
.cf-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.cf-time { font-family: monospace; font-size: 13px; color: var(--c-text-3); }
.cf-loading { display: flex; align-items: center; gap: 8px; color: var(--c-text-3); font-size: 13px; margin-top: 12px; }
.cf-explanation {
  margin-top: 12px; padding: 12px 14px; border-radius: 8px;
  background: var(--c-primary-soft); border: 1px solid var(--c-primary-border);
  font-size: 14px; line-height: 1.85; color: var(--c-text);
}
.vp-spinner {
  width: 14px; height: 14px; border-radius: 50%; display: inline-block;
  border: 2px solid var(--c-primary-border); border-top-color: var(--c-primary);
  animation: cf-spin .8s linear infinite;
}
@keyframes cf-spin { to { transform: rotate(360deg); } }

/* 深色模式：亮色主色底上用深色文字保证对比 */
html.dark .chapter-no,
html.dark .b-steps li::before { color: #08231f; }
html.dark .chat-msg.user .chat-bubble { color: #08231f; }
html.dark .b-table tr:nth-child(even) td { background: rgba(255,255,255,.02); }

/* 窄屏：隐藏侧边目录、自动降级为视频置顶 */
@media (max-width: 1000px) {
  .toc-side { display: none; }
  .note-main, .diagnosis-card, .intro-collapse, .quiz-entry { margin-left: 0; }
}
@media (max-width: 900px) {
  .layout.split { flex-direction: column; height: auto; overflow: visible; }
  .layout.split .video-panel { width: 100% !important; position: static; padding-right: 0; height: auto; overflow: visible; }
  .layout.split .content-panel { height: auto; overflow: visible; }
  .split-divider { display: none; }
}
</style>
