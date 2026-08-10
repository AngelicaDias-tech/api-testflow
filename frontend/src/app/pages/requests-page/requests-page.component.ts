import { Component, inject, signal } from '@angular/core'
import { ActivatedRoute, Router, RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import { MethodBadgeComponent } from '../../shared/method-badge/method-badge.component'
import type { RequestDef } from '../../core/models'

@Component({
  selector: 'app-requests-page',
  standalone: true,
  imports: [RouterLink, MethodBadgeComponent],
  template: `
    <div>
      <div class="mb-6 flex items-center justify-between">
        <div>
          <a routerLink="/" class="text-sm text-foreground-muted hover:text-foreground">← Projetos</a>
          <h1 class="text-2xl font-bold text-foreground">APIs testadas neste projeto</h1>
        </div>
        <button class="btn-primary" (click)="goNew()">🚀 Testar nova API</button>
      </div>

      @if (isLoading()) {
        <p class="text-foreground-muted">Carregando...</p>
      }

      @if (!isLoading() && requests().length === 0) {
        <div class="card p-10 text-center text-foreground-muted">Nenhuma API testada ainda neste projeto.</div>
      }

      <ul class="space-y-2">
        @for (r of requests(); track r.id) {
          <li class="card flex items-center justify-between p-4 transition-colors hover:border-primary/50">
            <a
              [routerLink]="['/projects', projectId, 'requests', r.id]"
              class="flex flex-1 items-center gap-3 overflow-hidden"
            >
              <app-method-badge [method]="r.method" />
              <div class="min-w-0">
                <p class="truncate font-medium text-foreground">{{ r.name }}</p>
                <p class="truncate text-xs text-foreground-muted mono">{{ r.url }}</p>
              </div>
            </a>
            <div class="flex items-center gap-3">
              @if (r.last_status_code) {
                <span class="badge {{ r.last_status_code < 400 ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger' }}">
                  HTTP {{ r.last_status_code }}
                </span>
              }
              <button class="text-xs text-foreground-muted hover:text-danger" (click)="onDelete(r)">excluir</button>
            </div>
          </li>
        }
      </ul>
    </div>
  `,
})
export class RequestsPageComponent {
  private api = inject(ApiService)
  private route = inject(ActivatedRoute)
  private router = inject(Router)

  projectId = this.route.snapshot.paramMap.get('projectId')!
  requests = signal<RequestDef[]>([])
  isLoading = signal(true)

  constructor() {
    this.reload()
  }

  private reload() {
    this.isLoading.set(true)
    this.api
      .listRequests(this.projectId)
      .then((requests) => this.requests.set(requests))
      .finally(() => this.isLoading.set(false))
  }

  goNew() {
    this.router.navigate(['/projects', this.projectId, 'new'])
  }

  async onDelete(r: RequestDef) {
    if (!confirm(`Excluir "${r.name}"?`)) return
    await this.api.deleteRequest(r.id)
    this.reload()
  }
}
