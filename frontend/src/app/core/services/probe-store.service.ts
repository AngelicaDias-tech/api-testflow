import { Injectable, WritableSignal, signal } from '@angular/core'
import type { ProbeResult } from '../models'

/**
 * Equivalente Angular do cache do React Query usado no frontend React
 * (chave ['probe', requestId], enabled:false) que corrigiu o bug de "o
 * JSON da API some ao voltar da tela de resultado".
 *
 * Por que existe: WorkbenchPageComponent é destruído/recriado toda vez que
 * o Angular Router navega para a tela de execução e volta (rotas
 * diferentes = componentes diferentes). Um signal local dentro do
 * componente reiniciaria como null nesse momento. Este serviço é
 * `providedIn: 'root'` — uma ÚNICA instância vive durante toda a sessão do
 * app, então o Map sobrevive à destruição/recriação do componente.
 *
 * Nunca faz nenhuma chamada HTTP sozinho: é só uma prateleira de cache
 * chaveada por requestId. A única forma de um valor aparecer aqui é o
 * usuário clicar explicitamente em "Testar API" (ver WorkbenchPageComponent
 * .testarApi(), que chama ApiService.probeRequest e grava o resultado
 * aqui) — voltar de uma tela nunca dispara uma nova chamada.
 */
@Injectable({ providedIn: 'root' })
export class ProbeStoreService {
  private store = new Map<string, WritableSignal<ProbeResult | null>>()

  signalFor(requestId: string): WritableSignal<ProbeResult | null> {
    let sig = this.store.get(requestId)
    if (!sig) {
      sig = signal<ProbeResult | null>(null)
      this.store.set(requestId, sig)
    }
    return sig
  }
}
