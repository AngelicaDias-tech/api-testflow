import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router'
import { RequestsPageComponent } from './requests-page.component'
import { ApiService } from '../../core/services/api.service'
import type { RequestDef } from '../../core/models'

describe('RequestsPageComponent — smoke', () => {
  let fixture: ComponentFixture<RequestsPageComponent>

  const requests: RequestDef[] = [
    {
      id: 'r1',
      project_id: 'p1',
      name: 'Hello World',
      method: 'GET',
      url: 'https://api.github.com/repos/octocat/Hello-World',
      headers: {},
      query_params: {},
      body: null,
      body_type: 'none',
      auth: { type: 'none' },
      is_mutating: false,
      created_at: '',
      updated_at: '',
      last_status_code: 200,
      last_response_time_ms: 100,
      last_probed_at: '',
    },
  ]

  beforeEach(async () => {
    const apiMock = { listRequests: jest.fn().mockResolvedValue(requests), deleteRequest: jest.fn() }
    TestBed.configureTestingModule({
      imports: [RequestsPageComponent],
      providers: [
        { provide: ApiService, useValue: apiMock },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ projectId: 'p1' }) } } },
        provideRouter([]),
      ],
    })
    fixture = TestBed.createComponent(RequestsPageComponent)
    fixture.detectChanges()
    await fixture.whenStable()
  })

  it('lista as requisições do projeto sem erro de template', () => {
    fixture.detectChanges()
    expect(fixture.componentInstance.requests()).toEqual(requests)
  })
})
