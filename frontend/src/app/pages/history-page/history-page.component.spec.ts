import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router'
import { HistoryPageComponent } from './history-page.component'
import { ApiService } from '../../core/services/api.service'
import type { ExecutionSummary } from '../../core/models'

describe('HistoryPageComponent — smoke', () => {
  let fixture: ComponentFixture<HistoryPageComponent>

  const executions: ExecutionSummary[] = [
    {
      id: 'exec-1',
      started_at: '2026-01-01T00:00:00',
      finished_at: '2026-01-01T00:00:01',
      duration_ms: 642.19,
      total: 4,
      passed: 4,
      failed: 0,
      skipped: 0,
      status: 'completed',
    },
  ]

  beforeEach(async () => {
    const apiMock = { listExecutions: jest.fn().mockResolvedValue(executions) }
    TestBed.configureTestingModule({
      imports: [HistoryPageComponent],
      providers: [
        { provide: ApiService, useValue: apiMock },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ projectId: 'p1', requestId: 'req-1' }) } } },
        provideRouter([]),
      ],
    })
    fixture = TestBed.createComponent(HistoryPageComponent)
    fixture.detectChanges()
    await fixture.whenStable()
    fixture.detectChanges()
  })

  it('lista o histórico de execuções sem erro de template', () => {
    expect(fixture.componentInstance.executions()).toEqual(executions)
  })
})
