import { Component, Input } from '@angular/core'

const COLORS: Record<string, string> = {
  GET: 'bg-success/15 text-success',
  POST: 'bg-warning/15 text-warning',
  PUT: 'bg-accent/15 text-accent',
  PATCH: 'bg-accent/15 text-accent',
  DELETE: 'bg-danger/15 text-danger',
}

@Component({
  selector: 'app-method-badge',
  standalone: true,
  template: `<span class="badge {{ cls() }} mono font-semibold">{{ method.toUpperCase() }}</span>`,
})
export class MethodBadgeComponent {
  @Input({ required: true }) method = ''

  cls(): string {
    return COLORS[this.method.toUpperCase()] ?? 'bg-card-hover text-foreground-muted'
  }
}
