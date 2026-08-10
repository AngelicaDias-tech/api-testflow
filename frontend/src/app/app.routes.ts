import { Routes } from '@angular/router'
import { ProjectsPageComponent } from './pages/projects-page/projects-page.component'
import { RequestsPageComponent } from './pages/requests-page/requests-page.component'
import { NewRequestPageComponent } from './pages/new-request-page/new-request-page.component'
import { WorkbenchPageComponent } from './pages/workbench-page/workbench-page.component'
import { HistoryPageComponent } from './pages/history-page/history-page.component'
import { ExecutionPageComponent } from './pages/execution-page/execution-page.component'

export const routes: Routes = [
  { path: '', component: ProjectsPageComponent },
  { path: 'projects/:projectId', component: RequestsPageComponent },
  { path: 'projects/:projectId/new', component: NewRequestPageComponent },
  { path: 'projects/:projectId/requests/:requestId', component: WorkbenchPageComponent },
  { path: 'projects/:projectId/requests/:requestId/history', component: HistoryPageComponent },
  {
    path: 'projects/:projectId/requests/:requestId/executions/:executionId',
    component: ExecutionPageComponent,
  },
]
