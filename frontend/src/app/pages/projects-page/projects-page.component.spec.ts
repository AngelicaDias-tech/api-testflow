import { ComponentFixture, TestBed } from '@angular/core/testing'
import { provideRouter } from '@angular/router'
import { ProjectsPageComponent } from './projects-page.component'
import { ApiService } from '../../core/services/api.service'
import type { Project } from '../../core/models'

describe('ProjectsPageComponent (Dashboard) — smoke', () => {
  let fixture: ComponentFixture<ProjectsPageComponent>
  let apiMock: { listProjects: jest.Mock; createProject: jest.Mock; deleteProject: jest.Mock }

  const projects: Project[] = [{ id: 'p1', name: 'Vivo', description: 'APIs do time de pagamentos', created_at: '' }]

  beforeEach(async () => {
    apiMock = {
      listProjects: jest.fn().mockResolvedValue(projects),
      createProject: jest.fn().mockResolvedValue({ id: 'p2', name: 'Novo', description: null, created_at: '' }),
      deleteProject: jest.fn().mockResolvedValue(undefined),
    }
    TestBed.configureTestingModule({
      imports: [ProjectsPageComponent],
      providers: [{ provide: ApiService, useValue: apiMock }, provideRouter([])],
    })
    fixture = TestBed.createComponent(ProjectsPageComponent)
    fixture.detectChanges()
    await fixture.whenStable()
  })

  it('carrega e mostra os projetos existentes sem erro de template', () => {
    fixture.detectChanges()
    expect(apiMock.listProjects).toHaveBeenCalledTimes(1)
    expect(fixture.componentInstance.projects()).toEqual(projects)
  })

  it('cria um projeto e recarrega a lista', async () => {
    fixture.componentInstance.name.set('Novo')
    await fixture.componentInstance.onCreate(new Event('submit'))
    expect(apiMock.createProject).toHaveBeenCalledWith('Novo', undefined)
    expect(apiMock.listProjects).toHaveBeenCalledTimes(2)
  })
})
