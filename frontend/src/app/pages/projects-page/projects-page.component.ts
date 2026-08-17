import { Component, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import { ApiError } from '../../core/services/api-error'
import type { ExportBundle, ImportSummary, Project } from '../../core/models'

@Component({
  selector: 'app-projects-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="mx-auto max-w-2xl">
      <div class="dashboard-shell mb-10 text-center">
        <div class="dashboard-hero-icon">🧪</div>
        <h1 class="dashboard-title">
          API <span class="dashboard-title-accent">TestFlow</span>
        </h1>
        <p class="dashboard-subtitle">Plataforma universal de testes automatizados de APIs</p>
      </div>

      <div class="mb-5 flex flex-wrap items-center justify-between gap-2">
        <h2 class="dashboard-section-title">Projetos</h2>
        <div class="flex items-center gap-2">
          <label class="btn-secondary cursor-pointer">
            📥 Importar testes
            <input class="hidden" type="file" accept="application/json,.json" (change)="onImportFileSelected($event)" />
          </label>
          <button class="btn-primary dashboard-btn-primary" (click)="showForm.set(!showForm())">+ Criar projeto</button>
        </div>
      </div>

      @if (importPending()) {
        <p class="mb-4 text-sm text-foreground-muted">Importando...</p>
      }
      @if (importError()) {
        <div class="banner-danger mb-4 text-sm">{{ importError() }}</div>
      }
      @if (importSummary(); as s) {
        <div class="banner-warning mb-4 text-sm">
          <p class="font-medium">
            ✅ Projeto "{{ s.project.name }}" importado: {{ s.requests_imported }} API(s),
            {{ s.rules_imported }} regra(s), {{ s.scenarios_imported }} cenário(s), {{ s.datasets_imported }} massa(s).
          </p>
          @for (w of s.warnings; track w) {
            <p class="mt-1">⚠️ {{ w }}</p>
          }
        </div>
      }

      @if (showForm()) {
        <form class="dashboard-form-card mb-6" (submit)="onCreate($event)">
          <div class="mb-3">
            <label class="label">Nome do projeto / squad</label>
            <input
              class="input"
              placeholder="Ex: Vivo, Porto, Claro..."
              [ngModel]="name()"
              (ngModelChange)="name.set($event)"
              name="name"
              autofocus
            />
          </div>
          <div class="mb-4">
            <label class="label">Descrição (opcional)</label>
            <input
              class="input"
              placeholder="Ex: APIs do time de pagamentos"
              [ngModel]="description()"
              (ngModelChange)="description.set($event)"
              name="description"
            />
          </div>
          <button class="btn-primary dashboard-btn-primary" type="submit" [disabled]="creating()">
            {{ creating() ? 'Criando...' : 'Criar projeto' }}
          </button>
        </form>
      }

      @if (isLoading()) {
        <p class="text-foreground-muted">Carregando...</p>
      }

      @if (!isLoading() && projects().length === 0) {
        <div class="dashboard-empty">
          <div class="dashboard-empty-icon">📁</div>
          Nenhum projeto ainda. Crie o primeiro para começar a testar suas APIs.
        </div>
      }

      <ul class="dashboard-list">
        @for (p of projects(); track p.id) {
          <li class="dashboard-card group">
            <a [routerLink]="['/projects', p.id]" class="flex flex-1 items-center gap-3 overflow-hidden">
              <span class="dashboard-card-avatar">{{ p.name.charAt(0).toUpperCase() }}</span>
              <span class="min-w-0">
                <p class="dashboard-card-name truncate">{{ p.name }}</p>
                @if (p.description) {
                  <p class="dashboard-card-desc truncate">{{ p.description }}</p>
                }
              </span>
            </a>
            <button class="dashboard-delete-btn mr-2 text-foreground-muted hover:text-foreground" (click)="onExport(p)">
              📤 exportar
            </button>
            <button class="dashboard-delete-btn" (click)="onDelete(p)">excluir</button>
          </li>
        }
      </ul>
    </div>
  `,
})
export class ProjectsPageComponent {
  private api = inject(ApiService)

  projects = signal<Project[]>([])
  isLoading = signal(true)
  creating = signal(false)
  name = signal('')
  description = signal('')
  showForm = signal(false)

  importPending = signal(false)
  importError = signal<string | null>(null)
  importSummary = signal<ImportSummary | null>(null)

  constructor() {
    this.reload()
  }

  private reload() {
    this.isLoading.set(true)
    this.api
      .listProjects()
      .then((projects) => this.projects.set(projects))
      .finally(() => this.isLoading.set(false))
  }

  async onCreate(e: Event) {
    e.preventDefault()
    if (!this.name().trim()) return
    this.creating.set(true)
    try {
      await this.api.createProject(this.name(), this.description() || undefined)
      this.name.set('')
      this.description.set('')
      this.showForm.set(false)
      this.reload()
    } finally {
      this.creating.set(false)
    }
  }

  async onDelete(p: Project) {
    if (!confirm(`Excluir o projeto "${p.name}"? Isso remove também suas requisições e testes.`)) return
    await this.api.deleteProject(p.id)
    this.reload()
  }

  async onExport(p: Project) {
    const bundle = await this.api.exportProject(p.id)
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `testflow-${p.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  onImportFileSelected(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    this.importError.set(null)
    this.importSummary.set(null)
    const reader = new FileReader()
    reader.onload = async () => {
      let bundle: ExportBundle
      try {
        bundle = JSON.parse(String(reader.result ?? ''))
      } catch {
        this.importError.set('Arquivo inválido: não é um JSON válido.')
        return
      }
      this.importPending.set(true)
      try {
        const summary = await this.api.importProject(bundle)
        this.importSummary.set(summary)
        this.reload()
      } catch (err) {
        this.importError.set(err instanceof ApiError ? err.message : (err as Error).message)
      } finally {
        this.importPending.set(false)
        input.value = ''
      }
    }
    reader.readAsText(file)
  }
}
