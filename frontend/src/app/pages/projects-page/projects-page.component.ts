import { Component, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import type { Project } from '../../core/models'

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

      <div class="mb-5 flex items-center justify-between">
        <h2 class="dashboard-section-title">Projetos</h2>
        <button class="btn-primary dashboard-btn-primary" (click)="showForm.set(!showForm())">+ Criar projeto</button>
      </div>

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
}
