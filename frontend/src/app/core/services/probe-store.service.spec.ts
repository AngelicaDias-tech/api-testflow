import { TestBed } from '@angular/core/testing'
import { ProbeStoreService } from './probe-store.service'
import type { ProbeResult } from '../models'

const mockProbe: ProbeResult = {
  status_code: 200,
  headers: {},
  content_type: 'application/json',
  body_raw: '{}',
  body_json: { name: 'Hello-World' },
  json_valid: true,
  response_time_ms: 10,
  error: null,
  discovered_checks: [],
}

describe('ProbeStoreService', () => {
  it('começa como null para um requestId nunca testado (nenhuma chamada HTTP automática)', () => {
    const service = TestBed.inject(ProbeStoreService)
    expect(service.signalFor('req-1')()).toBeNull()
  })

  it('grava e lê o probe pela mesma chave de requestId', () => {
    const service = TestBed.inject(ProbeStoreService)
    const sig = service.signalFor('req-2')
    sig.set(mockProbe)
    expect(service.signalFor('req-2')()).toEqual(mockProbe)
  })

  it('mantém o mesmo signal (mesma instância) entre múltiplas chamadas para o mesmo requestId — é isso que garante a persistência ao destruir/recriar o componente da tela', () => {
    const service = TestBed.inject(ProbeStoreService)
    const first = service.signalFor('req-3')
    first.set(mockProbe)

    // Simula o componente sendo destruído e recriado (nova chamada a
    // signalFor, como aconteceria no construtor de um novo
    // WorkbenchPageComponent após navegar para o resultado e voltar).
    const second = service.signalFor('req-3')

    expect(second).toBe(first)
    expect(second()).toEqual(mockProbe)
  })

  it('não mistura o probe de requisições diferentes', () => {
    const service = TestBed.inject(ProbeStoreService)
    service.signalFor('req-a').set(mockProbe)
    expect(service.signalFor('req-b')()).toBeNull()
  })
})
