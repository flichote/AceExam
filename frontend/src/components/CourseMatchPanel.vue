<template>
  <view class="panel">
    <!-- 1. 课程信息输入（联想 GET /courses/aliases → 匹配 POST /courses/match） -->
    <view class="card form">
      <view class="field">
        <text class="field-label">校本课程名 <text class="field-required">*</text></text>
        <input
          v-model="name"
          class="field-input"
          placeholder="如：清华 2026春 高等数学A"
          placeholder-class="field-placeholder"
          maxlength="100"
          @input="onNameInput"
          @focus="onNameInput"
        />
        <!-- 别名联想下拉 -->
        <view v-if="suggestions.length" class="suggest">
          <view
            v-for="s in suggestions"
            :key="s.alias"
            class="suggest-row"
            @click="onPickSuggestion(s)"
          >
            <text class="suggest-alias">{{ s.alias }}</text>
            <text class="suggest-arrow">→</text>
            <text class="suggest-template">{{ s.template_name }}</text>
            <text v-if="s.is_verified" class="suggest-verified">已收录</text>
          </view>
        </view>
      </view>

      <view class="field">
        <text class="field-label">学校（可选）</text>
        <input
          v-model="school"
          class="field-input"
          placeholder="如：清华大学"
          placeholder-class="field-placeholder"
          maxlength="100"
        />
      </view>

      <view class="field">
        <text class="field-label">教材（可选，辅助匹配）</text>
        <input
          v-model="textbook"
          class="field-input"
          placeholder="如：同济第七版"
          placeholder-class="field-placeholder"
          maxlength="100"
        />
      </view>

      <view
        class="btn btn--primary match-btn"
        :class="{ 'btn--disabled': matching || !name.trim() }"
        @click="runMatch"
      >
        <text class="match-btn-text">{{ matching ? "AI 匹配中…" : "智能匹配模板" }}</text>
      </view>
      <text class="match-tip">匹配到模板后，题目将跨校共享；模板可随时改选</text>
    </view>

    <!-- 2. 匹配成功（≥0.85 自动采用 top1；0.60~0.85 候选列表供选择） -->
    <template v-if="stage === 'matched'">
      <view class="card result">
        <view class="result-head">
          <text class="result-icon">✅</text>
          <view class="result-texts">
            <text class="result-title">{{ autoAdopt ? "已匹配到模板课程" : "找到相近的模板课程" }}</text>
            <text class="result-sub">
              {{ autoAdopt ? "置信度足够，已自动选中；可改选其他候选" : "请选择最接近的模板课程" }}
            </text>
          </view>
        </view>

        <view class="cand-list">
          <view
            v-for="c in candidates"
            :key="c.template_subject_id"
            class="cand"
            :class="{ 'cand--selected': selectedTemplateId === c.template_subject_id }"
            @click="selectedTemplateId = c.template_subject_id"
          >
            <view class="cand-radio">
              <text class="cand-radio-dot">{{ selectedTemplateId === c.template_subject_id ? "●" : "○" }}</text>
            </view>
            <view class="cand-info">
              <text class="cand-name">{{ c.name }}</text>
              <text class="cand-reason">{{ c.reason }}</text>
            </view>
            <view class="cand-conf" :class="confClass(c.confidence)">
              <text class="cand-conf-text">{{ Math.round(c.confidence * 100) }}%</text>
            </view>
          </view>
        </view>

        <view v-if="duplicateHint" class="dup-hint">
          <text class="dup-hint-text">⚠️ 该课程已在你的课程中，无需重复添加</text>
        </view>

        <view
          class="btn btn--primary add-btn"
          :class="{ 'btn--disabled': submitting }"
          @click="confirmAdd"
        >
          <text class="add-btn-text">{{ submitting ? "添加中…" : "确认添加" }}</text>
        </view>
      </view>
    </template>

    <!-- 3. 未匹配（<0.60 / 空候选）：手动建实例 或 手动指定模板 -->
    <template v-else-if="stage === 'nomatch'">
      <view class="card result">
        <view class="result-head">
          <text class="result-icon">🤔</text>
          <view class="result-texts">
            <text class="result-title">未匹配到合适的模板课程</text>
            <text class="result-sub">题库暂未覆盖该课程。可先作为独立校本课程录入，后续匹配到模板自动升级共享题库</text>
          </view>
        </view>

        <view class="nomatch-actions">
          <view class="action" @click="manualCreate">
            <text class="action-icon">🏫</text>
            <view class="action-texts">
              <text class="action-title">手动建独立课程</text>
              <text class="action-desc">以当前名称加入我的课程，题库仅自己可见</text>
            </view>
            <text class="action-arrow">›</text>
          </view>
          <view class="action" @click="openTemplatePicker">
            <text class="action-icon">📚</text>
            <view class="action-texts">
              <text class="action-title">手动指定模板</text>
              <text class="action-desc">从公共课程中选择最接近的模板映射（跨校共享）</text>
            </view>
            <text class="action-arrow">›</text>
          </view>
        </view>

        <!-- 模板选择（GET /subjects/plaza 公共模板） -->
        <view v-if="showTemplatePicker" class="picker">
          <text class="picker-title">选择模板课程</text>
          <view v-if="templatesLoading" class="picker-loading">
            <LoadingSkeleton />
          </view>
          <view
            v-for="t in templates"
            :key="t.id"
            class="cand"
            :class="{ 'cand--selected': selectedTemplateId === t.id }"
            @click="selectedTemplateId = t.id"
          >
            <view class="cand-radio">
              <text class="cand-radio-dot">{{ selectedTemplateId === t.id ? "●" : "○" }}</text>
            </view>
            <view class="cand-info">
              <text class="cand-name">{{ t.name }}</text>
              <text v-if="t.question_count > 0" class="cand-reason">{{ t.question_count }} 题</text>
              <text v-else class="cand-reason">题库建设中</text>
            </view>
          </view>
          <view
            class="btn btn--primary add-btn"
            :class="{ 'btn--disabled': submitting || !selectedTemplateId }"
            @click="confirmAdd"
          >
            <text class="add-btn-text">{{ submitting ? "添加中…" : "以所选模板添加" }}</text>
          </view>
        </view>
      </view>
    </template>

    <!-- 4. 添加成功（POST /me/courses 已返回） -->
    <template v-else-if="stage === 'done'">
      <view class="card result">
        <view class="result-head">
          <text class="result-icon">🎉</text>
          <view class="result-texts">
            <text class="result-title">已添加到「我的课程」</text>
            <text class="result-sub">「{{ doneSubjectName }}」已就绪，可在首页查看</text>
          </view>
        </view>

        <view class="done-tags">
          <view v-if="doneMatched" class="tag tag--success">
            <text class="tag-text">已映射到模板课程：{{ doneTemplateName }}</text>
          </view>
          <view v-else class="tag tag--info">
            <text class="tag-text">独立校本课程（暂未映射模板）</text>
          </view>
        </view>

        <view class="done-actions">
          <view class="btn btn--plain add-btn" @click="reset">
            <text class="add-btn-text">继续录入</text>
          </view>
          <view class="btn btn--primary add-btn" @click="$emit('added')">
            <text class="add-btn-text">完成</text>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type {
  CourseAliasItem,
  CourseMatchCandidate,
  CourseMatchResponse,
  PlazaSubject,
} from "@/types";
import { fetchCourseAliases, matchCourse, createMyCourse } from "@/api/courses";
import { fetchPlazaSubjects } from "@/api/subjects";
import LoadingSkeleton from "@/components/LoadingSkeleton.vue";

const emit = defineEmits<{ (e: "added"): void }>();

/** 录入流程阶段：input 输入 / matched 已匹配 / nomatch 未匹配 / done 添加成功 */
type Stage = "input" | "matched" | "nomatch" | "done";

const name = ref("");
const school = ref("");
const textbook = ref("");

const stage = ref<Stage>("input");
const matching = ref(false);
const submitting = ref(false);

const suggestions = ref<CourseAliasItem[]>([]);
const candidates = ref<CourseMatchCandidate[]>([]);
const selectedTemplateId = ref("");
const autoAdopt = ref(false);
const duplicateHint = ref(false);

const doneSubjectName = ref("");
const doneMatched = ref(false);
const doneTemplateName = ref("");

const showTemplatePicker = ref(false);
const templates = ref<PlazaSubject[]>([]);
const templatesLoading = ref(false);

let aliasTimer: ReturnType<typeof setTimeout> | undefined;
let aliasSeq = 0;

/** 输入联想：防抖 300ms 拉 GET /courses/aliases */
function onNameInput() {
  duplicateHint.value = false;
  if (aliasTimer) clearTimeout(aliasTimer);
  aliasTimer = setTimeout(async () => {
    const q = name.value.trim();
    const seq = ++aliasSeq;
    if (!q) {
      suggestions.value = [];
      return;
    }
    try {
      const items = await fetchCourseAliases(q, 8);
      if (seq === aliasSeq) suggestions.value = items;
    } catch {
      if (seq === aliasSeq) suggestions.value = [];
    }
  }, 300);
}

/** 点击别名联想：填入课程名并直接匹配 */
function onPickSuggestion(s: CourseAliasItem) {
  if (aliasTimer) clearTimeout(aliasTimer);
  aliasSeq++;
  suggestions.value = [];
  name.value = s.alias;
  runMatch();
}

/** POST /courses/match：按 D21 阈值分流 */
async function runMatch() {
  const trimmed = name.value.trim();
  if (!trimmed || matching.value) return;
  suggestions.value = [];
  duplicateHint.value = false;
  matching.value = true;
  stage.value = "input";
  try {
    const res = await matchCourse({
      name: trimmed,
      school: school.value.trim() || undefined,
      textbook: textbook.value.trim() || undefined,
      limit: 5,
    });
    applyMatch(res);
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "匹配失败", icon: "none" });
    stage.value = "input";
  } finally {
    matching.value = false;
  }
}

function applyMatch(res: CourseMatchResponse) {
  candidates.value = res.candidates || [];
  if (res.matched && candidates.value.length) {
    const top = candidates.value[0];
    autoAdopt.value = top.confidence >= 0.85;
    // ≥0.85 自动采用 top1（可改选）；0.60~0.85 预选 top1 供用户选择
    selectedTemplateId.value = top.template_subject_id;
    stage.value = "matched";
  } else {
    selectedTemplateId.value = "";
    autoAdopt.value = false;
    stage.value = "nomatch";
  }
}

/** 候选置信度徽标（token 色） */
function confClass(confidence: number): string {
  if (confidence >= 0.85) return "conf--high";
  if (confidence >= 0.6) return "conf--mid";
  return "conf--low";
}

/** 手动指定模板：懒加载广场公共模板 */
async function openTemplatePicker() {
  showTemplatePicker.value = true;
  if (templates.value.length || templatesLoading.value) return;
  templatesLoading.value = true;
  try {
    const res = await fetchPlazaSubjects();
    templates.value = res.items;
  } catch {
    templates.value = [];
  } finally {
    templatesLoading.value = false;
  }
}

/** 确认添加（映射模板）：POST /me/courses {template_subject_id} */
async function confirmAdd() {
  if (submitting.value || !selectedTemplateId.value) return;
  await doCreate(selectedTemplateId.value);
}

/** 手动建独立实例：POST /me/courses {template_subject_id: null} */
async function manualCreate() {
  if (submitting.value) return;
  await doCreate(null);
}

async function doCreate(templateSubjectId: string | null) {
  const trimmed = name.value.trim();
  if (!trimmed) {
    uni.showToast({ title: "请先填写课程名", icon: "none" });
    return;
  }
  submitting.value = true;
  duplicateHint.value = false;
  try {
    const res = await createMyCourse({
      name: trimmed,
      school: school.value.trim() || undefined,
      template_subject_id: templateSubjectId,
    });
    doneSubjectName.value = res.subject?.name || trimmed;
    doneMatched.value = !!res.matched;
    doneTemplateName.value =
      candidates.value.find((c) => c.template_subject_id === templateSubjectId)?.name ||
      templates.value.find((t) => t.id === templateSubjectId)?.name ||
      "";
    stage.value = "done";
  } catch (e) {
    const err = e as { code?: string };
    if (err.code === "ALREADY_EXISTS") {
      duplicateHint.value = true;
      uni.showToast({ title: "该课程已在你的课程中", icon: "none" });
    } else {
      uni.showToast({ title: (e as Error).message || "添加失败", icon: "none" });
    }
  } finally {
    submitting.value = false;
  }
}

/** 继续录入：清空表单回到输入态 */
function reset() {
  stage.value = "input";
  name.value = "";
  school.value = "";
  textbook.value = "";
  suggestions.value = [];
  candidates.value = [];
  selectedTemplateId.value = "";
  duplicateHint.value = false;
  showTemplatePicker.value = false;
  doneSubjectName.value = "";
  doneMatched.value = false;
  doneTemplateName.value = "";
}
</script>

<style lang="scss" scoped>
.panel {
  width: 100%;
}

/* 表单 */
.form {
  padding: 8rpx 28rpx 28rpx;
}
.field {
  padding: 20rpx 0;
  border-bottom: 2rpx solid $neutral-100;
  position: relative;
}
.field-label {
  display: block;
  font-size: 24rpx;
  color: $neutral-500;
  margin-bottom: 8rpx;
}
.field-required {
  color: $danger-500;
}
.field-input {
  font-size: $font-body;
  color: $neutral-900;
  padding: 8rpx 0;
}
.field-placeholder {
  color: $neutral-300;
}

/* 联想下拉 */
.suggest {
  position: absolute;
  left: -28rpx;
  right: -28rpx;
  top: 100%;
  background: #ffffff;
  border-radius: $radius-btn;
  box-shadow: $shadow-float;
  z-index: 20;
  max-height: 400rpx;
  overflow-y: auto;
}
.suggest-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx 28rpx;
  border-bottom: 2rpx solid $neutral-100;
}
.suggest-row:active {
  background: $primary-100;
}
.suggest-alias {
  font-size: $font-body;
  color: $neutral-900;
  font-weight: 600;
  flex-shrink: 0;
  max-width: 240rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suggest-arrow {
  color: $neutral-300;
  font-size: 22rpx;
}
.suggest-template {
  font-size: $font-body;
  color: $primary-600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suggest-verified {
  font-size: 20rpx;
  color: $success-500;
  background: rgba($success-500, 0.1);
  border-radius: $radius-tag;
  padding: 2rpx 10rpx;
  flex-shrink: 0;
}

/* 匹配按钮 */
.match-btn {
  margin-top: 28rpx;
  padding: 20rpx 0;
}
.match-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
  letter-spacing: 2rpx;
}
.match-tip {
  display: block;
  margin-top: 12rpx;
  font-size: 20rpx;
  color: $neutral-300;
  text-align: center;
}

/* 结果卡 */
.result {
  margin-top: 24rpx;
  padding: 28rpx;
}
.result-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}
.result-icon {
  font-size: 44rpx;
  flex-shrink: 0;
}
.result-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.result-title {
  font-size: $font-card-title;
  font-weight: 700;
  color: $neutral-900;
}
.result-sub {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 4rpx;
  line-height: 1.5;
}

/* 候选列表 */
.cand-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.cand {
  display: flex;
  align-items: center;
  gap: 12rpx;
  border: 2rpx solid $neutral-100;
  border-radius: $radius-btn;
  padding: 16rpx 20rpx;
  background: $neutral-100;
}
.cand--selected {
  border-color: $primary-500;
  background: $primary-100;
}
.cand-radio {
  flex-shrink: 0;
}
.cand-radio-dot {
  font-size: 32rpx;
  color: $primary-500;
}
.cand-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.cand-name {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.cand-reason {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.cand-conf {
  flex-shrink: 0;
  border-radius: $radius-tag;
  padding: 4rpx 14rpx;
}
.cand-conf-text {
  font-size: 22rpx;
  font-weight: 700;
}
.conf--high {
  background: rgba($success-500, 0.12);
}
.conf--high .cand-conf-text {
  color: $success-500;
}
.conf--mid {
  background: rgba($warning-500, 0.14);
}
.conf--mid .cand-conf-text {
  color: $warning-500;
}
.conf--low {
  background: rgba($danger-500, 0.1);
}
.conf--low .cand-conf-text {
  color: $danger-500;
}

/* 重复提示 */
.dup-hint {
  margin-top: 16rpx;
  background: rgba($warning-500, 0.12);
  border-radius: $radius-tag;
  padding: 10rpx 16rpx;
}
.dup-hint-text {
  font-size: 22rpx;
  color: $warning-500;
}

/* 添加按钮 */
.add-btn {
  margin-top: 24rpx;
  padding: 18rpx 0;
}
.add-btn-text {
  color: #ffffff;
  font-size: $font-body;
  font-weight: 700;
}

/* 未匹配操作 */
.nomatch-actions {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.action {
  display: flex;
  align-items: center;
  gap: 16rpx;
  border: 2rpx solid $neutral-100;
  border-radius: $radius-btn;
  padding: 20rpx;
}
.action:active {
  background: $neutral-100;
}
.action-icon {
  font-size: 40rpx;
  flex-shrink: 0;
}
.action-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.action-title {
  font-size: $font-body;
  font-weight: 700;
  color: $neutral-900;
}
.action-desc {
  font-size: 22rpx;
  color: $neutral-500;
  margin-top: 2rpx;
}
.action-arrow {
  font-size: 36rpx;
  color: $neutral-300;
}

/* 模板选择 */
.picker {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 2rpx solid $neutral-100;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.picker-title {
  font-size: 24rpx;
  color: $neutral-500;
}
.picker-loading {
  padding: 8rpx 0;
}

/* 成功标签 */
.done-tags {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.tag {
  border-radius: $radius-tag;
  padding: 12rpx 20rpx;
}
.tag--success {
  background: rgba($success-500, 0.12);
}
.tag--info {
  background: rgba($info-500, 0.1);
}
.tag-text {
  font-size: 24rpx;
  font-weight: 600;
}
.tag--success .tag-text {
  color: $success-500;
}
.tag--info .tag-text {
  color: $info-500;
}

/* 成功操作 */
.done-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 24rpx;
}
.done-actions .add-btn {
  flex: 1;
  margin-top: 0;
}
</style>
