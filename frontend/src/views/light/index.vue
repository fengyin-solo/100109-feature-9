<template>
  <section class="page" data-module="light">
    <header class="page-head">
      <div>
        <h2>路灯管养管理</h2>
        <p class="page-desc">按灯杆编号管理路灯台账与报修单据：报修修改即存即留、历史报修不覆盖，亮灯状态在台账、报修与养护三处同步。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreateLedger">登记路灯设施</button>
        <button class="btn" type="button" @click="exportRows">导出路灯管养清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- 路灯台账 -->
    <div v-show="activeTab === 'ledger'">
      <form class="filter-bar" @submit.prevent="reloadLedger">
        <label class="filter-item">
          <span>灯杆编号</span>
          <input v-model="ledgerFilter.keyword" placeholder="按灯杆编号检索" />
        </label>
        <label class="filter-item">
          <span>所在路段</span>
          <input v-model="ledgerFilter.road" placeholder="按所在路段检索" />
        </label>
        <label class="filter-item">
          <span>亮灯状态</span>
          <select v-model="ledgerFilter.status">
            <option value="">全部状态</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetLedgerFilter">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in ledgerColumns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ledgerRows" :key="String(row.id)">
            <td v-for="column in ledgerColumns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openCreateRepair(String(row['灯杆编号']))">报修登记</button>
              <button class="link" type="button" @click="openRepairHistory(String(row['灯杆编号']))">报修历史</button>
              <button class="link" type="button" @click="openEditLedger(row)">编辑台账</button>
            </td>
          </tr>
          <tr v-if="!ledgerRows.length">
            <td :colspan="ledgerColumns.length + 1" class="empty-state">暂无路灯管养数据，可先登记路灯设施</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ ledgerTotal }} 条路灯台账</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </div>

    <!-- 报修记录 -->
    <div v-show="activeTab === 'repairs'">
      <form class="filter-bar" @submit.prevent="reloadRepairs">
        <label class="filter-item">
          <span>灯杆编号</span>
          <input v-model="repairFilter.pole" placeholder="按灯杆编号检索" />
        </label>
        <label class="filter-item">
          <span>单据状态</span>
          <select v-model="repairFilter.status">
            <option value="">全部单据</option>
            <option v-for="status in docStatuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetRepairFilter">重置条件</button>
        <button class="btn primary" type="button" @click="openCreateRepair()">新增报修</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>报修单号</th>
            <th v-for="column in repairColumns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in repairRows" :key="String(row.id)">
            <td>#{{ row.id }}</td>
            <td v-for="column in repairColumns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openEditRepair(row)">编辑</button>
              <button
                v-if="row['单据状态'] === '已登记'"
                class="link"
                type="button"
                @click="dispatchRepair(row)"
              >
                安排维修
              </button>
              <button
                v-if="row['单据状态'] !== '已修复'"
                class="link"
                type="button"
                @click="openCompleteRepair(row)"
              >
                完成维修
              </button>
            </td>
          </tr>
          <tr v-if="!repairRows.length">
            <td :colspan="repairColumns.length + 2" class="empty-state">暂无报修记录</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ repairTotal }} 条报修记录（历史报修永久保留，不会被新报修覆盖）</span>
      </footer>
    </div>

    <!-- 养护记录 -->
    <div v-show="activeTab === 'maintenance'">
      <form class="filter-bar" @submit.prevent="reloadMaintenance">
        <label class="filter-item">
          <span>灯杆编号</span>
          <input v-model="maintenanceFilter.pole" placeholder="按灯杆编号检索" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetMaintenanceFilter">重置条件</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th>养护单号</th>
            <th v-for="column in maintenanceColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in maintenanceRows" :key="String(row.id)">
            <td>#{{ row.id }}</td>
            <td v-for="column in maintenanceColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!maintenanceRows.length">
            <td :colspan="maintenanceColumns.length + 1" class="empty-state">暂无养护记录（填写处理情况并完成维修后生成）</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ maintenanceTotal }} 条养护记录</span></footer>
    </div>

    <!-- 灯型更换记录 -->
    <div v-show="activeTab === 'changes'">
      <form class="filter-bar" @submit.prevent="reloadChanges">
        <label class="filter-item">
          <span>灯杆编号</span>
          <input v-model="changeFilter.pole" placeholder="按灯杆编号检索" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetChangeFilter">重置条件</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in changeColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in changeRows" :key="String(row.id)">
            <td v-for="column in changeColumns" :key="column">{{ row[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!changeRows.length">
            <td :colspan="changeColumns.length" class="empty-state">暂无灯型类别更换记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 报修弹窗（新增 / 编辑共用；打开时回填已保存内容） -->
    <div v-if="repairDialog.open" class="modal-mask" @click.self="closeRepairDialog">
      <div class="modal">
        <h3 class="modal-title">{{ repairDialog.mode === 'create' ? '报修登记' : `编辑报修单 #${repairDialog.form.id}` }}</h3>
        <p class="modal-hint">故障类型与报修日期只挂在对应灯杆编号上；保存后再次打开仍是这一份。</p>
        <div class="form-grid">
          <label class="form-item">
            <span>灯杆编号 <em>*</em></span>
            <input v-if="repairDialog.mode === 'create'" list="pole-options" v-model="repairDialog.form.灯杆编号" placeholder="选择或输入灯杆编号" />
            <input v-else :value="repairDialog.form.灯杆编号" readonly />
          </label>
          <label class="form-item">
            <span>故障类型 <em>*</em></span>
            <select v-model="repairDialog.form.故障类型">
              <option v-for="fault in faultTypes" :key="fault" :value="fault">{{ fault }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>报修日期 <em>*</em></span>
            <input v-model="repairDialog.form.报修日期" type="date" />
          </label>
          <label class="form-item">
            <span>亮灯状态</span>
            <select v-model="repairDialog.form.亮灯状态">
              <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
            </select>
          </label>
          <label class="form-item form-wide">
            <span>处理情况</span>
            <textarea v-model="repairDialog.form.处理情况" rows="3" placeholder="记录现场核查、处置措施与复核结论"></textarea>
          </label>
          <label class="form-item form-wide">
            <span>更换灯型类别</span>
            <input v-model="repairDialog.form.更换灯型类别" placeholder="如本次维修更换了灯型再填写，留空表示不更换" />
          </label>
        </div>
        <datalist id="pole-options">
          <option v-for="pole in poleOptions" :key="pole" :value="pole"></option>
        </datalist>
        <p v-if="repairDialog.error" class="error-text">{{ repairDialog.error }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeRepairDialog">取消</button>
          <button class="btn primary" type="button" :disabled="repairDialog.saving" @click="saveRepair">
            {{ repairDialog.saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 完成维修弹窗：处理情况必填 -->
    <div v-if="completeDialog.open" class="modal-mask" @click.self="completeDialog.open = false">
      <div class="modal">
        <h3 class="modal-title">完成维修 · {{ completeDialog.form.灯杆编号 }}（报修单 #{{ completeDialog.form.id }}）</h3>
        <div class="form-grid">
          <label class="form-item form-wide">
            <span>处理情况 <em>*</em></span>
            <textarea v-model="completeDialog.form.处理情况" rows="3" placeholder="请填写维修处理情况，保存后同步到养护记录"></textarea>
          </label>
          <label class="form-item form-wide">
            <span>更换灯型类别</span>
            <input v-model="completeDialog.form.更换灯型类别" placeholder="如更换了灯型再填写，系统将自动登记灯型更换记录" />
          </label>
        </div>
        <p v-if="completeDialog.error" class="error-text">{{ completeDialog.error }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="completeDialog.open = false">取消</button>
          <button class="btn primary" type="button" :disabled="completeDialog.saving" @click="saveComplete">确认完成维修</button>
        </div>
      </div>
    </div>

    <!-- 台账登记 / 编辑弹窗 -->
    <div v-if="ledgerDialog.open" class="modal-mask" @click.self="ledgerDialog.open = false">
      <div class="modal">
        <h3 class="modal-title">{{ ledgerDialog.mode === 'create' ? '登记路灯设施' : `编辑路灯台账 · ${ledgerDialog.form.灯杆编号}` }}</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>灯杆编号 <em>*</em></span>
            <input v-model="ledgerDialog.form.灯杆编号" :readonly="ledgerDialog.mode === 'edit'" />
          </label>
          <label class="form-item">
            <span>所在路段 <em>*</em></span>
            <input v-model="ledgerDialog.form.所在路段" />
          </label>
          <label class="form-item">
            <span>灯型类别 <em>*</em></span>
            <input v-model="ledgerDialog.form.灯型类别" placeholder="改动灯型类别会自动登记一条更换记录" />
          </label>
          <label class="form-item">
            <span>功率瓦数</span>
            <input v-model="ledgerDialog.form.功率瓦数" />
          </label>
          <label class="form-item">
            <span>亮灯时段</span>
            <input v-model="ledgerDialog.form.亮灯时段" />
          </label>
          <label v-if="ledgerDialog.mode === 'edit'" class="form-item">
            <span>亮灯状态</span>
            <select v-model="ledgerDialog.form.亮灯状态">
              <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
            </select>
          </label>
        </div>
        <p v-if="ledgerDialog.error" class="error-text">{{ ledgerDialog.error }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="ledgerDialog.open = false">取消</button>
          <button class="btn primary" type="button" :disabled="ledgerDialog.saving" @click="saveLedger">
            {{ ledgerDialog.saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 单杆报修历史弹窗 -->
    <div v-if="historyDialog.open" class="modal-mask" @click.self="historyDialog.open = false">
      <div class="modal modal-wide">
        <h3 class="modal-title">{{ historyDialog.pole }} 的报修历史</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>单号</th>
              <th v-for="column in repairColumns" :key="column">{{ column }}</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in historyDialog.rows" :key="String(row.id)">
              <td>#{{ row.id }}</td>
              <td v-for="column in repairColumns" :key="column">{{ row[column] ?? '—' }}</td>
              <td><button class="link" type="button" @click="openEditRepairFromHistory(row)">编辑此单</button></td>
            </tr>
            <tr v-if="!historyDialog.rows.length">
              <td :colspan="repairColumns.length + 2" class="empty-state">该灯杆暂无报修记录</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="historyDialog.open = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/light'
const ledgerColumns = ['灯杆编号', '所在路段', '灯型类别', '功率瓦数', '亮灯时段', '故障类型', '报修日期', '亮灯状态']
const repairColumns = ['灯杆编号', '故障类型', '报修日期', '处理情况', '更换灯型类别', '单据状态', '亮灯状态']
const maintenanceColumns = ['灯杆编号', '故障类型', '报修日期', '处理情况', '更换灯型类别', '亮灯状态']
const changeColumns = ['灯杆编号', '原灯型类别', '新灯型类别', '更换日期']

const statuses = ref<string[]>([])
const faultTypes = ref<string[]>([])
const docStatuses = ref<string[]>([])
const poleOptions = ref<string[]>([])
const stats = ref<{ label: string; value: number }[]>([
  { label: '正常亮灯', value: 0 },
  { label: '故障路灯', value: 0 },
  { label: '维修中路灯', value: 0 },
])

const tabs = [
  { key: 'ledger', label: '路灯台账' },
  { key: 'repairs', label: '报修记录' },
  { key: 'maintenance', label: '养护记录' },
  { key: 'changes', label: '灯型更换记录' },
] as const
type TabKey = (typeof tabs)[number]['key']
const activeTab = ref<TabKey>('ledger')

const errorMessage = ref('')

// ------------------------------------------------------------- 台账
const ledgerRows = ref<Row[]>([])
const ledgerTotal = ref(0)
const ledgerFilter = reactive({ keyword: '', road: '', status: '' })

function resetLedgerFilter() {
  ledgerFilter.keyword = ''
  ledgerFilter.road = ''
  ledgerFilter.status = ''
  void reloadLedger()
}

async function reloadLedger() {
  const params = new URLSearchParams()
  if (ledgerFilter.keyword) params.set('keyword', ledgerFilter.keyword)
  if (ledgerFilter.road) params.set('road', ledgerFilter.road)
  if (ledgerFilter.status) params.set('status', ledgerFilter.status)
  const response = await request(`${ENDPOINT}?${params.toString()}`)
  if (!response.ok) throw new Error('路灯设施列表读取失败')
  const payload = await response.json()
  ledgerRows.value = payload.items ?? []
  ledgerTotal.value = payload.total ?? ledgerRows.value.length
}

// ------------------------------------------------------------- 报修
const repairRows = ref<Row[]>([])
const repairTotal = ref(0)
const repairFilter = reactive({ pole: '', status: '' })

function resetRepairFilter() {
  repairFilter.pole = ''
  repairFilter.status = ''
  void reloadRepairs()
}

async function reloadRepairs() {
  const params = new URLSearchParams()
  if (repairFilter.pole) params.set('pole', repairFilter.pole)
  if (repairFilter.status) params.set('status', repairFilter.status)
  const response = await request(`${ENDPOINT}/repairs?${params.toString()}`)
  if (!response.ok) throw new Error('报修记录列表读取失败')
  const payload = await response.json()
  repairRows.value = payload.items ?? []
  repairTotal.value = payload.total ?? repairRows.value.length
}

// ------------------------------------------------------------- 养护
const maintenanceRows = ref<Row[]>([])
const maintenanceTotal = ref(0)
const maintenanceFilter = reactive({ pole: '' })

function resetMaintenanceFilter() {
  maintenanceFilter.pole = ''
  void reloadMaintenance()
}

async function reloadMaintenance() {
  const params = new URLSearchParams()
  if (maintenanceFilter.pole) params.set('pole', maintenanceFilter.pole)
  const response = await request(`${ENDPOINT}/maintenances?${params.toString()}`)
  if (!response.ok) throw new Error('养护记录列表读取失败')
  const payload = await response.json()
  maintenanceRows.value = payload.items ?? []
  maintenanceTotal.value = payload.total ?? maintenanceRows.value.length
}

// ------------------------------------------------------------- 灯型更换
const changeRows = ref<Row[]>([])
const changeFilter = reactive({ pole: '' })

function resetChangeFilter() {
  changeFilter.pole = ''
  void reloadChanges()
}

async function reloadChanges() {
  const params = new URLSearchParams()
  if (changeFilter.pole) params.set('pole', changeFilter.pole)
  const response = await request(`${ENDPOINT}/type-changes?${params.toString()}`)
  if (!response.ok) throw new Error('灯型更换记录读取失败')
  const payload = await response.json()
  changeRows.value = payload.items ?? []
}

// ------------------------------------------------------------- 统计与元数据
async function reloadStats() {
  const response = await request(`${ENDPOINT}/stats`)
  if (!response.ok) return
  const payload = await response.json()
  if (Array.isArray(payload.items)) stats.value = payload.items
}

async function reloadMeta() {
  const response = await request(`${ENDPOINT}/meta`)
  if (!response.ok) return
  const meta = await response.json()
  statuses.value = meta.statuses ?? []
  faultTypes.value = meta.fault_types ?? []
  docStatuses.value = meta.doc_statuses ?? []
}

async function reloadPoleOptions() {
  const response = await request(`${ENDPOINT}?size=200`)
  if (!response.ok) return
  const payload = await response.json()
  poleOptions.value = (payload.items as Row[]).map((row) => String(row['灯杆编号'] ?? ''))
}

async function refreshAll() {
  errorMessage.value = ''
  try {
    await Promise.all([
      reloadLedger(),
      reloadRepairs(),
      reloadMaintenance(),
      reloadChanges(),
      reloadStats(),
      reloadPoleOptions(),
    ])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '路灯管养数据读取失败'
  }
}

function switchTab(tab: TabKey) {
  activeTab.value = tab
}

// ------------------------------------------------------------- 报修弹窗
interface RepairForm {
  id: number | null
  灯杆编号: string
  故障类型: string
  报修日期: string
  处理情况: string
  更换灯型类别: string
  亮灯状态: string
}

const repairDialog = reactive({
  open: false,
  mode: 'create' as 'create' | 'edit',
  saving: false,
  error: '',
  form: emptyRepairForm(),
})

function emptyRepairForm(): RepairForm {
  return {
    id: null,
    灯杆编号: '',
    故障类型: '',
    报修日期: '',
    处理情况: '',
    更换灯型类别: '',
    亮灯状态: '故障不亮',
  }
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

async function openCreateRepair(poleNo = '') {
  repairDialog.mode = 'create'
  repairDialog.error = ''
  repairDialog.form = emptyRepairForm()
  repairDialog.form.灯杆编号 = poleNo
  repairDialog.form.故障类型 = faultTypes.value[0] ?? ''
  repairDialog.form.报修日期 = today()
  repairDialog.form.亮灯状态 = '故障不亮'
  repairDialog.open = true
}

async function openEditRepair(row: Row) {
  repairDialog.mode = 'edit'
  repairDialog.error = ''
  repairDialog.form = emptyRepairForm()
  // 关键：再次打开时按单号回读服务端已保存的那份，不用列表上的旧快照。
  const response = await request(`${ENDPOINT}/repairs/${row.id}`)
  if (!response.ok) {
    repairDialog.error = '报修记录读取失败，请稍后重试'
    repairDialog.open = true
    return
  }
  const saved = await response.json()
  repairDialog.form = {
    id: Number(saved.id),
    灯杆编号: String(saved['灯杆编号'] ?? ''),
    故障类型: String(saved['故障类型'] ?? ''),
    报修日期: String(saved['报修日期'] ?? ''),
    处理情况: String(saved['处理情况'] ?? ''),
    更换灯型类别: String(saved['更换灯型类别'] ?? ''),
    亮灯状态: String(saved['亮灯状态'] ?? '故障不亮'),
  }
  repairDialog.open = true
}

function closeRepairDialog() {
  repairDialog.open = false
}

async function saveRepair() {
  const form = repairDialog.form
  if (!form.灯杆编号.trim()) {
    repairDialog.error = '请选择或填写灯杆编号'
    return
  }
  if (!form.故障类型) {
    repairDialog.error = '请选择故障类型'
    return
  }
  if (!form.报修日期) {
    repairDialog.error = '请填写报修日期'
    return
  }
  repairDialog.saving = true
  repairDialog.error = ''
  try {
    const values: Record<string, string> = {
      故障类型: form.故障类型,
      报修日期: form.报修日期,
      处理情况: form.处理情况,
      亮灯状态: form.亮灯状态,
    }
    if (form.更换灯型类别.trim()) values.更换灯型类别 = form.更换灯型类别.trim()
    const url = repairDialog.mode === 'create'
      ? `${ENDPOINT}/repairs`
      : `${ENDPOINT}/repairs/${form.id}`
    const method = repairDialog.mode === 'create' ? 'POST' : 'PUT'
    if (repairDialog.mode === 'create') values.灯杆编号 = form.灯杆编号.trim()
    const response = await request(url, { method, body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? '报修内容未保存，请稍后重试')
    }
    repairDialog.open = false
    await refreshAll()
  } catch (error) {
    repairDialog.error = error instanceof Error ? error.message : '报修内容保存失败'
  } finally {
    repairDialog.saving = false
  }
}

// ------------------------------------------------------------- 完成维修弹窗
const completeDialog = reactive({
  open: false,
  saving: false,
  error: '',
  form: { id: 0, 灯杆编号: '', 处理情况: '', 更换灯型类别: '' },
})

function openCompleteRepair(row: Row) {
  completeDialog.error = ''
  completeDialog.form = {
    id: Number(row.id),
    灯杆编号: String(row['灯杆编号'] ?? ''),
    处理情况: '',
    更换灯型类别: '',
  }
  completeDialog.open = true
}

async function saveComplete() {
  if (!completeDialog.form.处理情况.trim()) {
    completeDialog.error = '请填写处理情况后再完成维修'
    return
  }
  completeDialog.saving = true
  completeDialog.error = ''
  try {
    const values: Record<string, string> = { action: '完成维修', 处理情况: completeDialog.form.处理情况.trim() }
    if (completeDialog.form.更换灯型类别.trim()) values.更换灯型类别 = completeDialog.form.更换灯型类别.trim()
    const response = await request(`${ENDPOINT}/repairs/${completeDialog.form.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? '维修完成动作未生效')
    }
    completeDialog.open = false
    await refreshAll()
  } catch (error) {
    completeDialog.error = error instanceof Error ? error.message : '维修完成动作失败'
  } finally {
    completeDialog.saving = false
  }
}

async function dispatchRepair(row: Row) {
  const response = await request(`${ENDPOINT}/repairs/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action: '安排维修' } }),
  })
  const payload = await response.json()
  if (!response.ok || payload.ok === false) {
    errorMessage.value = payload.message ?? '安排维修未生效'
    return
  }
  await refreshAll()
}

// ------------------------------------------------------------- 台账弹窗
interface LedgerForm {
  id: number | null
  灯杆编号: string
  所在路段: string
  灯型类别: string
  功率瓦数: string
  亮灯时段: string
  亮灯状态: string
}

const ledgerDialog = reactive({
  open: false,
  mode: 'create' as 'create' | 'edit',
  saving: false,
  error: '',
  form: { id: null, 灯杆编号: '', 所在路段: '', 灯型类别: '', 功率瓦数: '', 亮灯时段: '', 亮灯状态: '正常亮灯' } as LedgerForm,
})

function openCreateLedger() {
  ledgerDialog.mode = 'create'
  ledgerDialog.error = ''
  ledgerDialog.form = { id: null, 灯杆编号: '', 所在路段: '', 灯型类别: '', 功率瓦数: '', 亮灯时段: '', 亮灯状态: '正常亮灯' }
  ledgerDialog.open = true
}

function openEditLedger(row: Row) {
  ledgerDialog.mode = 'edit'
  ledgerDialog.error = ''
  ledgerDialog.form = {
    id: Number(row.id),
    灯杆编号: String(row['灯杆编号'] ?? ''),
    所在路段: String(row['所在路段'] ?? ''),
    灯型类别: String(row['灯型类别'] ?? ''),
    功率瓦数: String(row['功率瓦数'] ?? ''),
    亮灯时段: String(row['亮灯时段'] ?? ''),
    亮灯状态: String(row['亮灯状态'] ?? '正常亮灯'),
  }
  ledgerDialog.open = true
}

async function saveLedger() {
  const form = ledgerDialog.form
  if (!form.灯杆编号.trim() || !form.所在路段.trim() || !form.灯型类别.trim()) {
    ledgerDialog.error = '灯杆编号、所在路段、灯型类别为必填项'
    return
  }
  ledgerDialog.saving = true
  ledgerDialog.error = ''
  try {
    const values: Record<string, string> = {
      灯杆编号: form.灯杆编号.trim(),
      所在路段: form.所在路段.trim(),
      灯型类别: form.灯型类别.trim(),
      功率瓦数: form.功率瓦数.trim(),
      亮灯时段: form.亮灯时段.trim(),
    }
    const url = ledgerDialog.mode === 'create' ? ENDPOINT : `${ENDPOINT}/${form.id}`
    const method = ledgerDialog.mode === 'create' ? 'POST' : 'PUT'
    if (ledgerDialog.mode === 'edit') values.亮灯状态 = form.亮灯状态
    const response = await request(url, { method, body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message ?? '台账内容未保存')
    }
    ledgerDialog.open = false
    await refreshAll()
  } catch (error) {
    ledgerDialog.error = error instanceof Error ? error.message : '台账保存失败'
  } finally {
    ledgerDialog.saving = false
  }
}

// ------------------------------------------------------------- 报修历史
const historyDialog = reactive({ open: false, pole: '', rows: [] as Row[] })

async function openRepairHistory(poleNo: string) {
  historyDialog.pole = poleNo
  historyDialog.open = true
  const response = await request(`${ENDPOINT}/repairs?pole=${encodeURIComponent(poleNo)}&size=200`)
  if (!response.ok) {
    historyDialog.rows = []
    return
  }
  const payload = await response.json()
  historyDialog.rows = payload.items ?? []
}

async function openEditRepairFromHistory(row: Row) {
  historyDialog.open = false
  await openEditRepair(row)
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

onMounted(refreshAll)
</script>

<style scoped>
.tab-bar { display: flex; gap: 4px; margin-bottom: 12px; border-bottom: 1px solid var(--border); }
.tab-item { border: none; background: none; padding: 8px 16px; cursor: pointer; font-size: 14px; color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tab-item.active { color: var(--brand); border-bottom-color: var(--brand); font-weight: 600; }

.filter-item select,
.form-item input,
.form-item select,
.form-item textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  font-family: inherit;
  background: #fff;
}
.filter-item select { min-width: 120px; }

.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 10px; padding: 20px 24px; width: 560px; max-width: calc(100vw - 32px); max-height: 88vh; overflow-y: auto; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2); }
.modal-wide { width: 960px; }
.modal-title { margin: 0 0 4px; font-size: 16px; }
.modal-hint { margin: 0 0 14px; font-size: 12px; color: var(--muted); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; }
.form-item { display: flex; flex-direction: column; gap: 4px; }
.form-item span { font-size: 12px; color: var(--muted); }
.form-item em { color: #b42318; font-style: normal; }
.form-item input[readonly] { background: #f1f5f9; color: var(--muted); }
.form-wide { grid-column: 1 / -1; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
</style>
