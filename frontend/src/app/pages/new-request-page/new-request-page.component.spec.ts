import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router'
import { NewRequestPageComponent } from './new-request-page.component'
import { ApiService } from '../../core/services/api.service'

describe('NewRequestPageComponent — smoke', () => {
  let fixture: ComponentFixture<NewRequestPageComponent>
  let apiMock: { createRequest: jest.Mock; probeRequest: jest.Mock; importCurl: jest.Mock; importBruno: jest.Mock }

  beforeEach(() => {
    apiMock = {
      createRequest: jest.fn().mockResolvedValue({ id: 'req-9' }),
      probeRequest: jest.fn().mockResolvedValue({}),
      importCurl: jest.fn(),
      importBruno: jest.fn(),
    }
    TestBed.configureTestingModule({
      imports: [NewRequestPageComponent],
      providers: [
        { provide: ApiService, useValue: apiMock },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ projectId: 'p1' }) } } },
        provideRouter([]),
      ],
    })
    fixture = TestBed.createComponent(NewRequestPageComponent)
    fixture.detectChanges()
  })

  it('renderiza os 3 modos (manual/cURL/Bruno) sem erro de template', () => {
    expect(fixture.componentInstance.tab()).toBe('manual')
    fixture.componentInstance.tab.set('curl')
    fixture.detectChanges()
    fixture.componentInstance.tab.set('bruno')
    fixture.detectChanges()
  })

  it('mostra o aviso de método mutante e cria a requisição sem probe automático de mutante', async () => {
    fixture.componentInstance.method.set('POST')
    fixture.componentInstance.url.set('https://api.exemplo.com/x')
    fixture.detectChanges()
    expect(fixture.componentInstance.isMutating()).toBe(true)

    await fixture.componentInstance.onSubmit()
    expect(apiMock.createRequest).toHaveBeenCalledTimes(1)
    expect(apiMock.probeRequest).not.toHaveBeenCalled()
  })
})
