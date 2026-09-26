<template>
  <section class="page" data-module="light">
    <header class="page-head">
      <div>
        <h2>路灯管养管理</h2>
        <p class="page-desc">维护路灯设施，围绕灯杆编号、所在路段、灯型类别、功率瓦数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" :class="{ primary: viewMode === 'records' }" @click="switchView(viewMode === 'records' ? 'ledger' : 'records')">
          {{ viewMode === 'records' ? '返回路灯台账' : '查看养护记录' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出路灯管养清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <!-- 按亮灯状态分组：台账、报修弹窗、养护记录共用后端同一份口径 -->
    <div class="group-tabs" role="tablist">
      <button
        class="group-tab"
        type="button"
        :class="{ active: activeStatus === '' }"
        @click="filterByStatus('')"
      >
        全部<span class="tab-count">{{ total }}</span>
      </button>
      <button
        v-for="status in statuses"
        :key="status"
        class="group-tab"
        type="button"
        :class="{ active: activeStatus === status }"
        @click="filterByStatus(status)"
      >
        {{ status }}<span class="tab-count">{{ groups[status] ?? 0 }}</span>
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>灯杆编号</span>
        <input v-model="keyword" placeholder="按灯杆编号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <!-- 路灯台账 -->
    <table v-if="viewMode === 'ledger'" class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openReport(row)">报修登记</button>
            <button class="link" type="button" @click="runAction('安排维修', row)">安排维修</button>
            <button class="link" type="button" @click="runAction('完成维修', row)">完成维修</button>
            <button class="link" type="button" @click="openHistory(row)">历史报修</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无路灯管养数据</td>
        </tr>
      </tbody>
    </table>

    <!-- 养护记录：每一次报修都是独立一条，亮灯状态实时取自台账 -->
    <table v-else class="data-table">
      <thead>
        <tr>
          <th v-for="column in repairColumns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in repairRows" :key="String(row.id)">
          <td v-for="column in repairColumns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openEdit(row)">修改报修</button>
          </td>
        </tr>
        <tr v-if="!repairRows.length">
          <td :colspan="repairColumns.length + 1" class="empty-state">暂无养护记录，可先在台账里登记报修</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ viewMode === 'ledger' ? total : repairRows.length }} 条{{ viewMode === 'ledger' ? '路灯管养' : '养护' }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 报修弹窗 / 修改报修弹窗 -->
    <div v-if="dialogOpen" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3 class="modal-title">{{ editing ? '修改报修记录' : '路灯报修登记' }}</h3>
        <p class="modal-sub">
          灯杆编号：<strong>{{ form.lightCode }}</strong>
          <span v-if="editing">· 报修记录 #{{ form.id }}</span>
        </p>
        <div class="modal-body">
          <label class="form-item">
            <span>故障类型 <em>*</em></span>
            <input v-model="form.fault" list="fault-options" placeholder="如：灯具不亮 / 灯杆倾斜" />
            <datalist id="fault-options">
              <option v-for="fault in faultOptions" :key="fault" :value="fault" />
            </datalist>
          </label>
          <label class="form-item">
            <span>报修日期</span>
            <input v-model="form.reportDate" type="date" />
          </label>
          <label class="form-item">
            <span>处理情况</span>
            <textarea v-model="form.handleResult" rows="3" placeholder="填写本次报修的处理情况"></textarea>
          </label>
          <label class="form-item">
            <span>更换灯型类别</span>
            <input v-model="form.newLampType" list="lamp-options" placeholder="更换过灯型时填写，如：LED 灯 / 高压钠灯" />
            <datalist id="lamp-options">
              <option v-for="lamp in lampOptions" :key="lamp" :value="lamp" />
            </datalist>
          </label>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" :disabled="saving" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="submitDialog">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 历史报修抽屉式弹窗：历史记录只展示，不被新报修覆盖 -->
    <div v-if="historyOpen" class="modal-mask" @click.self="historyOpen = false">
      <div class="modal">
        <h3 class="modal-title">历史报修记录</h3>
        <p class="modal-sub">灯杆编号：<strong>{{ historyLightCode }}</strong>（共 {{ historyRows.length }} 条，新报修不覆盖历史）</p>
        <ul class="history-list">
          <li v-for="record in historyRows" :key="record.id" class="history-item">
            <div class="history-head">
              <span class="history-tag">#{{ record.id }} · {{ record.报修日期 || '未填日期' }}</span>
              <span class="history-status">{{ record.亮灯状态 }}</span>
            </div>
            <div class="history-line">故障类型：{{ record.故障类型 || '—' }}</div>
            <div class="history-line">处理情况：{{ record.处理情况 || '—' }}</div>
            <div class="history-line" v-if="record.更换灯型类别">更换灯型类别：{{ record.更换灯型类别 }}</div>
            <button class="link history-edit" type="button" @click="openEdit(record, true)">修改这条</button>
          </li>
          <li v-if="!historyRows.length" class="empty-state">该灯杆暂无报修记录</li>
        </ul>
        <div class="modal-foot">
          <button class="btn primary" type="button" @click="historyOpen = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface RepairRow {
  [key: string]: string | number | null
  id: number
  light_id: number
  灯杆编号: string
  所在路段: string | null
  灯型类别: string | null
  报修日期: string | null
  故障类型: string | null
  处理情况: string | null
  更换灯型类别: string | null
  亮灯状态: string
}

const ENDPOINT = '/api/light'
const columns = ['灯杆编号', '所在路段', '灯型类别', '功率瓦数', '亮灯时段', '故障类型', '报修日期', '亮灯状态']
const repairColumns = ['灯杆编号', '所在路段', '灯型类别', '报修日期', '故障类型', '处理情况', '更换灯型类别', '亮灯状态']
const statuses = ['正常亮灯', '故障不亮', '维修中', '已拆除']
const faultOptions = ['灯具不亮', '灯泡烧毁', '灯杆倾斜', '线路故障', '控制器故障', '灯罩破损']
const lampOptions = ['LED 灯', '高压钠灯', '金卤灯', '节能灯', '太阳能灯']

const rows = ref<Row[]>([])
const repairRows = ref<RepairRow[]>([])
const total = ref(0)
const groups = ref<Record<string, number>>({})
const errorMessage = ref('')
const keyword = ref('')
const activeStatus = ref('')
const viewMode = ref<'ledger' | 'records'>('ledger')

const statCards = computed(() => [
  { label: '正常亮灯', value: groups.value['正常亮灯'] ?? 0 },
  { label: '故障路灯', value: groups.value['故障不亮'] ?? 0 },
  { label: '维修中路灯', value: groups.value['维修中'] ?? 0 },
])

// ---- 报修 / 修改弹窗 ----
const dialogOpen = ref(false)
const saving = ref(false)
const editing = ref(false)
const fromHistory = ref(false)
const form = ref({
  id: 0,
  lightId: 0,
  lightCode: '',
  fault: '',
  reportDate: '',
  handleResult: '',
  newLampType: '',
})

// ---- 历史报修弹窗 ----
const historyOpen = ref(false)
const historyRows = ref<RepairRow[]>([])
const historyLightCode = ref('')

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

async function loadGroups() {
  try {
    const response = await request(`${ENDPOINT}/groups`)
    if (response.ok) {
      groups.value = (await response.json()).groups ?? {}
    }
  } catch {
    // 分组加载失败不阻塞列表
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (activeStatus.value) params.set('status', activeStatus.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('路灯设施列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路灯管养列表读取失败'
  }
  await loadGroups()
}

async function reloadRepairs() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (activeStatus.value) params.set('status', activeStatus.value)
  try {
    const response = await request(`${ENDPOINT}/repairs?${params.toString()}`)
    if (!response.ok) throw new Error('养护记录读取失败')
    repairRows.value = (await response.json()).items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护记录读取失败'
  }
  await loadGroups()
}

async function switchView(target: 'ledger' | 'records') {
  viewMode.value = target
  if (target === 'records') await reloadRepairs()
  else await reload()
}

function filterByStatus(status: string) {
  activeStatus.value = status
  void (viewMode.value === 'records' ? reloadRepairs() : reload())
}

function resetFilters() {
  keyword.value = ''
  activeStatus.value = ''
  void (viewMode.value === 'records' ? reloadRepairs() : reload())
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openReport(row: Row) {
  editing.value = false
  fromHistory.value = false
  form.value = {
    id: 0,
    lightId: Number(row.id),
    lightCode: String(row['灯杆编号'] ?? ''),
    fault: '',
    reportDate: todayISO(),
    handleResult: '',
    newLampType: '',
  }
  dialogOpen.value = true
}

function openEdit(record: RepairRow, fromHistoryDialog = false) {
  editing.value = true
  fromHistory.value = fromHistoryDialog
  form.value = {
    id: record.id,
    lightId: record.light_id,
    lightCode: record.灯杆编号,
    fault: record.故障类型 ?? '',
    reportDate: record.报修日期 ?? '',
    handleResult: record.处理情况 ?? '',
    newLampType: record.更换灯型类别 ?? '',
  }
  dialogOpen.value = true
}

function closeDialog() {
  dialogOpen.value = false
}

async function submitDialog() {
  errorMessage.value = ''
  if (!form.value.fault.trim()) {
    errorMessage.value = '故障类型不能为空'
    return
  }
  saving.value = true
  const values: Record<string, string> = {
    故障类型: form.value.fault.trim(),
    报修日期: form.value.reportDate || todayISO(),
    处理情况: form.value.handleResult.trim(),
    更换灯型类别: form.value.newLampType.trim(),
  }
  try {
    const url = editing.value
      ? `${ENDPOINT}/repairs/${form.value.id}`
      : `${ENDPOINT}/${form.value.lightId}/repairs`
    const response = await request(url, {
      method: editing.value ? 'PUT' : 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.message || '报修记录未保存，请稍后重试')
    }
    dialogOpen.value = false
    await reload()
    if (viewMode.value === 'records') await reloadRepairs()
    if (historyOpen.value) await loadHistory(form.value.lightId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '报修记录保存失败'
  } finally {
    saving.value = false
  }
}

async function loadHistory(lightId: number) {
  try {
    const response = await request(`${ENDPOINT}/${lightId}/repairs`)
    if (!response.ok) throw new Error('历史报修读取失败')
    historyRows.value = (await response.json()).items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '历史报修读取失败'
  }
}

async function openHistory(row: Row) {
  historyLightCode.value = String(row['灯杆编号'] ?? '')
  await loadHistory(Number(row.id))
  historyOpen.value = true
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.message || '路灯管养动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路灯管养操作失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
}

.group-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid #d4d9e0;
  border-radius: 999px;
  background: #fff;
  color: #4b5563;
  cursor: pointer;
  font-size: 13px;
}

.group-tab.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.tab-count {
  font-weight: 600;
  font-size: 12px;
  opacity: 0.85;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 24px;
}

.modal {
  width: min(520px, 100%);
  max-height: 86vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
}

.modal-title {
  margin: 0;
  font-size: 17px;
}

.modal-sub {
  margin: 6px 0 14px;
  color: #6b7280;
  font-size: 13px;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #374151;
}

.form-item em {
  color: #dc2626;
  font-style: normal;
}

.form-item input,
.form-item textarea {
  padding: 7px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font: inherit;
  resize: vertical;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: #374151;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.history-tag {
  font-weight: 600;
  color: #1f2937;
}

.history-status {
  padding: 1px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
}

.history-line {
  line-height: 1.7;
}

.history-edit {
  margin-top: 6px;
  padding: 0;
}
</style>
