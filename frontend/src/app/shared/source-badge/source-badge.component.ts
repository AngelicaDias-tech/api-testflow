import { Component, Input } from '@angular/core'

@Component({
  selector: 'app-source-badge',
  standalone: true,
  template: `
    @if (source === 'auto') {
      <span class="badge-auto">automático</span>
    } @else if (source === 'ai_suggested') {
      <span class="badge-ai">🤖 IA</span>
    } @else {
      <span class="badge-custom">manual</span>
    }
  `,
})
export class SourceBadgeComponent {
  @Input({ required: true }) source = ''
}
