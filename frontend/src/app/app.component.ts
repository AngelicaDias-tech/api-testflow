import { Component } from '@angular/core'
import { RouterLink, RouterOutlet } from '@angular/router'

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <div class="min-h-screen bg-canvas">
      <header class="app-header">
        <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a routerLink="/" class="flex items-center gap-2 text-lg font-bold text-foreground">
            <span>🧪</span>
            <span>API <span class="text-primary">TestFlow</span></span>
          </a>
          <p class="hidden text-sm text-foreground-muted sm:block">
            Teste sua API de forma automática — sem escrever código
          </p>
        </div>
      </header>
      <main class="mx-auto max-w-6xl px-6 py-8">
        <router-outlet />
      </main>
    </div>
  `,
})
export class AppComponent {}
