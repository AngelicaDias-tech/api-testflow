import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router'
import { ExecutionPageComponent } from './execution-page.component'
import { ApiService } from '../../core/services/api.service'
import type { Execution } from '../../core/models'

describe('ExecutionPageComponent — smoke (PASS/FAIL/SKIPPED vindo do pytest real)', () => {
  let fixture: ComponentFixture<ExecutionPageComponent>

  const execution: Execution = {
    id: 'exec-1',
    request_id: 'req-1',
    started_at: '2026-01-01T00:00:00',
    finished_at: '2026-01-01T00:00:01',
    duration_ms: 642.19,
    total: 2,
    passed: 1,
    failed: 1,
    skipped: 0,
    status: 'completed',
    error_message: null,
    results: [
      {
        id: 'res-1',
        execution_id: 'exec-1',
        rule_id: 'rule-1',
        node_id: 'test_check[rule-1]',
        name: 'stargazers_count greater_than 100',
        source: 'custom',
        category: 'field',
        field: 'stargazers_count',
        operator: 'greater_than',
        expected: '100',
        actual: '3755',
        outcome: 'passed',
        message: 'stargazers_count greater_than',
        duration_ms: 0.8,
      },
      {
        id: 'res-2',
        execution_id: 'exec-1',
        rule_id: 'rule-2',
        node_id: 'test_check[rule-2]',
        name: 'forks_count less_than 1',
        source: 'custom',
        category: 'field',
        field: 'forks_count',
        operator: 'less_than',
        expected: '1',
        actual: '6445',
        outcome: 'failed',
        message: 'assert 6445 < 1',
        duration_ms: 0.6,
      },
    ],
  }

  beforeEach(async () => {
    const apiMock = { getExecution: jest.fn().mockResolvedValue(execution), aiExplainFailure: jest.fn() }
    TestBed.configureTestingModule({
      imports: [ExecutionPageComponent],
      providers: [
        { provide: ApiService, useValue: apiMock },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: convertToParamMap({ projectId: 'p1', requestId: 'req-1', executionId: 'exec-1' }) },
          },
        },
        provideRouter([]),
      ],
    })
    fixture = TestBed.createComponent(ExecutionPageComponent)
    fixture.detectChanges()
    await fixture.whenStable()
    fixture.detectChanges()
  })

  it('mostra PASS/FAIL vindos do pytest real, sem a IA decidir nada', () => {
    expect(fixture.componentInstance.execution()!.passed).toBe(1)
    expect(fixture.componentInstance.execution()!.failed).toBe(1)
  })

  it('seleciona um resultado e mostra expected/actual', () => {
    fixture.componentInstance.select(execution.results[1])
    fixture.detectChanges()
    expect(fixture.componentInstance.selected()!.outcome).toBe('failed')
  })
})
