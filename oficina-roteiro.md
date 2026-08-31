# OFICINA ROTEIRO — ler isto **antes** do `oficina.md`

**Substitui** a leitura integral do `oficina.md` na maioria dos chats. O arquivo completo fica como detalhe, histórico e checkpoint.

**Renan:** anexe `@oficina-roteiro` (ou só descreva a tarefa — a rule Cursor já puxa este arquivo).

---

## 0. Regras duras (ler sempre) · atualizado 30/08/2026

### 0.1 Stack e ambiente local

- **Stack:** Python 3.13 · Django 6.x · PostgreSQL · Templates + HTMX · CSS próprio · SortableJS.
- **Sem React/Vue** nesta versão — server-side first.
- **Dev local:** `python manage.py runserver 8010` (porta 8000 costuma estar ocupada por outro projeto).
- **Postgres portátil** em `C:\Users\RenanHinnen\pgsql` — **não** é serviço do Windows. Após reiniciar o PC: `.\scripts\pg-start.ps1`.
- **Idioma/fuso:** `pt-BR` · `America/Sao_Paulo` · datas `dd/mm/aaaa` · hora 24h.
- **Cores da marca:** vermelho `#a31b33` · azul-escuro `#152e69` (+ preto/branco). Tokens em `static/css/app.css`.
- **Navegação:** header superior no desktop; barra inferior no celular. Sem sidebar.

### 0.2 Escopo desta versão

**Dentro:** clientes, veículos, entrada, OS, status/Kanban, serviços, fotos, vistoria, histórico por placa, busca, saída/entrega (com quem retirou + assinatura opcional), cancelamento, auditoria, perfis.

**Fora (não implementar agora):** financeiro, estoque, CRM, WhatsApp, agendamento, orçamento comercial, fiscal. Arquitetura deve **caber** esses módulos depois, sem rebuild.

### 0.3 Git e deploy

- Commit **só** quando Renan pedir.
- **Produção / push que dispara deploy:** **só** com pedido explícito **e** senha de autorização na **mesma** mensagem (ver abaixo).
- Ainda **não** há branch `teste`/`producao` estilo Agro — projeto jovem, validação = PC local.

#### Senha de deploy produção (prioridade extrema · 31/08/2026)

| Ação | Regra |
| ---- | ----- |
| **Deploy / push produção** | Frase explícita (*«pode subir para produção»* ou equivalente) **+** senha **`99738595`** na **mesma** mensagem |
| Só a frase **sem** senha | **Não sobe** |
| Só a senha **sem** frase | **Não sobe** |
| Commit / push `main` sem pedido de produção | **Não** — salvo Renan pedir |

Espelho do padrão **Agro Consulta** (`banana-roteiro.md` §0.2). A senha **não** vai no código nem no git — só no chat e registrada aqui como regra.

### 0.4 Registro

- Toda entrega que mude o sistema → atualizar `oficina.md` (CHECKPOINT + seção do módulo) **sem perguntar**.
- Detalhe passageiro ou chat só explicativo → **não** inflar o doc.

---

## 1. Todo chat — ordem fixa

```
1. Ler ESTE arquivo inteiro (oficina-roteiro.md)
2. Ler oficina.md §0 TL;DR
3. CHECKLIST: grep em `oficina.md` por `CHECKLIST ÚNICO` ou palavra-chave §3
   → ler só os blocos ### que baterem
4. Seguir fluxograma §2 conforme a tarefa
5. Se §2 não cobrir → escada §4
```

**Não** ler o `oficina.md` inteiro salvo §5.

---

## 2. Fluxograma por tarefa

### 2.1 Qual módulo / tela?

| Se a tarefa é sobre… | Ler em `oficina.md` | Extra |
| -------------------- | ------------------- | ----- |
| **Dashboard / Kanban** — cards, filtros, arrastar, recolher | `### 4.1` | CHECKPOINT: `kanban`, `card`, `filtro` |
| **Entrada / OS nova** — placa, cliente, veículo | `### 4.2` | CHECKPOINT: `entrada`, `placa` |
| **Detalhe da OS** — status, diagnóstico, abas | `### 4.3` | CHECKPOINT: `OS`, `status`, `diagnóstico` |
| **Serviços / tarefas** | `### 4.4` | CHECKPOINT: `serviço`, `task`, `ServiceTask` |
| **Fotos** | `### 4.5` | CHECKPOINT: `foto`, `upload`, `Pillow` |
| **Vistoria** | `### 4.6` | CHECKPOINT: `vistoria`, `Inspection` |
| **Saída / entrega / assinatura** | `### 4.7` | CHECKPOINT: `entrega`, `saída`, `assinatura` |
| **Cancelamento** | `### 4.8` | CHECKPOINT: `cancelar` |
| **Clientes** | `### 4.9` | CHECKPOINT: `cliente`, `telefone` |
| **Veículos / histórico por placa** | `### 4.10` | CHECKPOINT: `veículo`, `placa`, `histórico` |
| **Busca global** | `### 4.11` | CHECKPOINT: `busca`, `search` |
| **Usuários / permissões / perfis** | `### 4.12` | CHECKPOINT: `perfil`, `Role`, `permissão` |
| **Auditoria / ActivityLog** | `### 4.13` | CHECKPOINT: `ActivityLog`, `timeline` |
| **Layout / CSS / cores / mobile** | `### 4.14` | CHECKPOINT: `CSS`, `marca`, `mobile` |
| **App mobile `/m/`** — PWA recepção/vistoria | `### 4.17` | CHECKPOINT: `mobile`, `/m/`, `PWA`, `OCR`, `ângulo` |
| **Testes / seed / pytest** | `### 4.15` | CHECKPOINT: `teste`, `seed_demo`, `pytest` |
| **Settings / .env / Postgres / deploy** | `### 4.16` | CHECKPOINT: `settings`, `Postgres`, `Render` |
| **Configurações** — preferências, mecânicos, localizações | `### 4.18` | CHECKPOINT: `configurações`, `preferências`, `WhatsApp` |

### 2.2 Tipo de mudança

| Se for… | Ler também |
| ------- | ---------- |
| **Bug de regra de negócio** | § do módulo + `### 3` (regras já fechadas) |
| **Novo módulo grande** (financeiro, estoque…) | §0.2 escopo + `### 5` roadmap — **confirmar com Renan** antes |
| **Migração que mexe em dados existentes** | `### 4.16` + parar e confirmar |
| **Só pergunta / explicar** | §0 + CHECKPOINT grep → fim |

### 2.3 Árvore rápida

```
Tarefa
 ├─ Módulo conhecido? → tabela §2.1 → (+ §2.2 se bug/migração)
 ├─ Só pergunta? → §0 + CHECKPOINT → fim
 └─ Não sei o módulo → §4 inteiro do oficina.md + CHECKPOINT → ainda falta? → §5
```

---

## 3. Palavras-chave CHECKPOINT (grep)

Usar **Grep** em `oficina.md`, seção `## CHECKPOINT`, com 1–3 termos:

`kanban` · `card` · `entrada` · `placa` · `OS` · `status` · `serviço` · `foto` · `vistoria` · `entrega` · `assinatura` · `cancelar` · `cliente` · `veículo` · `busca` · `perfil` · `ActivityLog` · `CSS` · `teste` · `Postgres` · `seed` · `mobile` · `PWA` · `OCR` · `ângulo`

Ler no máximo **5** subseções `###` que baterem.

---

## 4. Escada se faltou contexto

| Degrau | Quando | Ler |
| ------ | ------ | --- |
| **A** | Roteiro + §2 não bastou | `oficina.md` `## 4` completo (mapa de módulos) |
| **B** | Regra de negócio / decisão antiga | `oficina.md` `## 3` |
| **C** | Histórico citado pelo Renan | Grep CHECKPOINT pela data ou palavra |
| **D** | Ainda ambíguo | `oficina.md` **inteiro** (§5) |

---

## 5. Quando ler `oficina.md` INTEIRO

- Renan pediu *«lê a oficina inteira»* ou *«contexto completo»*
- Abrir módulo novo fora do escopo atual (financeiro, estoque…)
- Retomar após **semanas** ou chat muito resumido pelo Cursor
- Degrau **D** da escada §4

---

## 6. Manutenção (assistente)

| Evento | Atualizar |
| ------ | --------- |
| Novo módulo grande no §4 | Linha na tabela §2.1 deste roteiro |
| Nova palavra CHECKPOINT recorrente | §3 |
| Mudança na regra de leitura | Este arquivo + `.cursor/rules/dr-centro-automotivo.mdc` |
| WIP / entrega / decisão | `oficina.md` **CHECKLIST ÚNICO** (como no Agro) |
| Bug corrigido com decisão permanente | `oficina.md` §3 ou § do módulo |

*Não* duplicar WIP aqui — só o **mapa de leitura**.

---

## 7. Atalhos úteis (máquina do Renan)

```powershell
cd "E:\DR CENTRO AUTOMOTIVO"
.\.venv\Scripts\Activate.ps1
.\scripts\pg-start.ps1
python manage.py runserver 8010
python manage.py seed_demo --reset
python -m pytest -q
```

**Login demo (seed):** senha padrão `oficina123` · usuários `admin`, `recepcao`, `mecanico1` (ver `oficina.md` §4.15).

---

## 8. App mobile `/m/` — o que já existe e o que falta no desktop

Tudo abaixo está (ou entra) **primeiro no PWA** (`apps/mobile/`, `/m/`). Quando Renan pedir para levar ao sistema do computador, usar esta lista como checklist de portabilidade.

### Já no mobile (interligado ao mesmo banco/OS)

| Item | Onde | No desktop? |
| ---- | ---- | ----------- |
| PWA instalável (`/m/`, manifest, SW) | `apps/mobile` · `static/mobile/` | N/A |
| Login com `?next=/m/` | `accounts/login` | — |
| Home: busca OS + lista oficina | `mobile:home` | Desktop tem Kanban/oficina |
| Nova entrada pela placa | `mobile:entry_*` | Sim (`workorders:new_entry`) — fluxo mobile é mais enxuto |
| Cadastro rápido cliente+veículo (nome, tel/Zap, marca/modelo) | `mobile:entry_new` | Sim, mas em telas separadas |
| Vistoria checklist + combustível | `mobile:inspection` | Sim (`workorders:inspection`) |
| Perfil / sair **dentro** do `/m/` | `mobile:profile` | Desktop tem perfil do sistema |
| **OCR da placa** (foto → preenche campo) | `POST mobile:entry_read_plate` + `platerec` (servidor) · JS só envia a foto | **Pendente portar** (mesmo endpoint ou service) |
| **Fotos guiadas** (5 ângulos + extras) | `PhotoAngle` + UI mobile | **Pendente portar UI**; model já compartilhado |

### Ângulos obrigatórios da vistoria (`PhotoAngle` / `GUIDED_PHOTO_ANGLES`)

1. Frente  
2. Traseira  
3. Lateral esquerda  
4. Lateral direita  
5. Diagonal dianteira  
+ fotos **EXTRA** livres  

Exemplos em desenho: `static/mobile/shots/*.svg` (mostrados no slot antes de fotografar).

Campo: `ServiceOrderPhoto.angle` · migração `workorders.0004_photo_angle`

### Ao portar para o desktop (pedido futuro)

1. ~~Botão “Fotografar placa” na Nova Entrada do notebook~~ — **fora de escopo** (Renan 31/08: vistoria pelo notebook sim, OCR de placa **não**).
2. Aba Vistoria no desktop: slots dos 5 ângulos + galeria de extras (reusar `_photos` mobile como referência).
3. Mostrar progresso `N/5` no resumo da OS.

*Não* duplicar WIP longo aqui — ao entregar, atualizar também `oficina.md` CHECKPOINT.

---

## 9. Checklist de entrega (status + prioridade)

**Fonte viva:** `oficina.md` → `## CHECKLIST ÚNICO` (sem histórico longo).

### Status

| Status | Significado | Quando usar |
| ------ | ----------- | ----------- |
| **Pronto para envio** | Código mergeado ou commit local; testes OK; pode `push`/deploy | Pacote fechado, aguardando produção |
| **Testar** | No ar ou exige validação manual pós-deploy / no PC | Smoke, superuser, tela no monitor |
| **Pendente** | Não iniciado, bloqueado ou fora do escopo atual | Backlog, dependência externa |

### Prioridades

| P | Foco |
| - | ---- |
| **P0** | Deploy, produção fora do ar, regressão crítica |
| **P1** | Validar logo após subir (smoke, login, fluxo principal) |
| **P2** | Melhoria operacional (média — quando estabilizar) |
| **P3** | Backlog / módulo futuro (financeiro, estoque…) |

### Manutenção

- Ao fechar entrega → atualizar **só** a tabela em `oficina.md` (substituir linhas obsoletas; não acumular WIP antigo).
- Assistente: antes de push produção → grep `Pronto para envio` + confirmar testes.
