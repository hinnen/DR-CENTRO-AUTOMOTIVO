# OFICINA — DR Centro Automotivo (anexe com `@oficina`)

Sistema web de gestão **operacional** da oficina mecânica **DR Centro Automotivo**.
Controla o veículo da chegada até a entrega.

**Este é o anexo de contexto vivo do projeto.** Leitura guiada: **`oficina-roteiro.md`**
(ler **antes** deste arquivo). A rule Cursor em `.cursor/rules/dr-centro-automotivo.mdc`
puxa o roteiro automaticamente.

| Você quer… | Faça |
| ---------- | ---- |
| Retomar trabalho / novo chat | `@oficina-roteiro` (ou só descrever a tarefa) |
| Detalhe fino / histórico / WIP | `@oficina` + grep CHECKPOINT |
| Registrar onde paramos | Automático no fim da entrega; ou *"atualize a oficina"* |
| README humano (instalação) | `README.md` |

**Assistente:** 1ª ação = ler **`oficina-roteiro.md` inteiro** e seguir o fluxograma
(trechos deste arquivo, **não** o arquivo todo — ver roteiro §5). Registrar alterações
aqui **sem pedir** quando entregar código ou decisão permanente.

**Commit:** só quando Renan pedir. **Deploy / push produção:** só com pedido explícito.

---

## 0. TL;DR (leia em 1 minuto)

| Item | Valor |
| ---- | ----- |
| **Produto** | DR Centro Automotivo — gestão operacional de oficina |
| **Usuários** | Administrador, Recepção, Mecânico |
| **Stack** | Python 3.13 · Django 6.x · PostgreSQL · Templates + HTMX · CSS próprio · SortableJS |
| **Workspace** | `E:\DR CENTRO AUTOMOTIVO` |
| **Dev** | `runserver 8010` · Postgres portátil `.\scripts\pg-start.ps1` |
| **Regra de ouro** | Em segundos: onde está o carro, quem mexeu, há quanto tempo, o que falta |
| **UX** | Poucos cliques · desktop + mobile · marca vermelho/azul-escuro · nav superior |
| **Fora de escopo agora** | Financeiro, estoque, CRM, WhatsApp, agendamento, fiscal |
| **Testes** | `pytest` · suíte verde (30/08/2026) |
| **Fases 1–13** | Concluídas (núcleo operacional) |

---

## 1. O negócio (não técnico)

A oficina precisa **saber onde está cada carro** sem depender da memória do pátio.

Fluxo típico:

1. Carro chega → recepção registra **entrada** pela placa
2. Vistoria + fotos do estado de chegada
3. OS sobe no **Kanban** (avaliação → aprovação/peça → manutenção → finalizado)
4. Mecânico registra diagnóstico e **serviços** (tarefas)
5. Serviço pronto = **Finalizado** (carro ainda na oficina)
6. Cliente busca = **Entregue** (KM de saída; opcional: quem retirou + assinatura)
7. Histórico fica na **placa** para a próxima visita

**Perfis:**

| Perfil | Faz | Não faz |
| ------ | --- | ------- |
| **Administrador** | Tudo | — |
| **Recepção** | Clientes, veículos, entrada, OS, fotos, vistoria, saída, cancelar | Admin de usuários; (exclusões fortes só admin) |
| **Mecânico** | Ver OS, diagnóstico, serviços, fotos, vistoria, mover status no quadro | Cadastrar cliente, registrar saída, cancelar OS, apagar fotos |

---

## 2. Arquitetura técnica

```
[Navegador]
     ↓ HTTP
[Django config/] ──→ apps/
        │              ├─ core/        bases, permissões, seed, erros
        │              ├─ accounts/    User + Role
        │              ├─ customers/   Client
        │              ├─ vehicles/    Vehicle + VehicleLocation
        │              ├─ workorders/  OS, status, tasks, fotos, vistoria, entrega
        │              └─ dashboard/   Kanban + filtros
[PostgreSQL]  ← DATABASE_URL (senão SQLite só p/ clone inicial)
[WhiteNoise] estáticos · media local em DEBUG
```

### 2.1 Onde vive a regra de negócio

- **Services:** `apps/workorders/services.py` (e `customers/services.py`, `vehicles/services.py`)
- **Views** só orquestram form → service → redirect/partial
- **Permissões:** properties no `User` + `RoleRequiredMixin` / `capability_required`
- **Templates** podem esconder botão; **nunca** são a fonte da autorização

### 2.2 Apps e papéis

| App | Papel |
| --- | ----- |
| `core` | `BaseModel`, utils (telefone/placa), permissões, `seed_demo`, erros 403/404/500 |
| `accounts` | `User` (`AbstractUser` + Role), login/logout/perfil |
| `customers` | Cliente (nome, telefone normalizado, CPF/CNPJ) |
| `vehicles` | Veículo (placa normalizada), localização física |
| `workorders` | OS, histórico de status, tarefas, fotos, vistoria, entrega, ActivityLog |
| `dashboard` | Painel + Kanban + partial HTMX do quadro |

---

## 3. Regras de negócio já fechadas

1. **Placa** normalizada (maiúsculas, sem hífen/espaço); aceita antigo e Mercosul.
2. **Telefone** só dígitos; remove `+55` redundante.
3. **Número de OS** único via `OrderNumberCounter` + `SELECT FOR UPDATE`; cancelar **não** devolve número.
4. **Status** só via `transition_service_order_status` (histórico na mesma transação).
5. **Kanban** move só os 6 status do quadro. Entrega e cancelamento **não** entram pelo drag.
6. **Finalizado ≠ Entregue.** Finalizado = pronto na oficina. Entregue = saiu.
7. **Tempo** na oficina / no status é **calculado**, não gravado.
8. **Drag** pede; backend valida com trava; `409` → card volta.
9. **ServiceTask** = linha individual; cancelada sai do denominador do progresso.
10. **Foto** = soft-delete; nome no storage = UUID.
11. **Upload** validado: extensão + MIME + Pillow.
12. **KM saída < entrada** exige justificativa (não bloqueia cegamente).
13. **Quem retirou** (nome, documento, assinatura) = **opcional**.
14. **OS não apaga** — cancela com motivo.
15. **Checklist de vistoria** copia rótulo no item (histórico imutável se a lista padrão mudar).
16. **ActivityLog** = fonte da timeline; admin somente leitura.

---

## 4. Mapa de módulos

### 4.1 Dashboard / Kanban

- Templates: `templates/dashboard/home.html`, `partials/_board.html`, `_order_card.html`, `_filters.html`
- JS: `static/js/kanban.js` (Sortable + abas mobile + recolher/expandir cards)
- CSS: `.kanban` coluna min `280px`; card expandido `268px` / recolhido `76px`
- Polling HTMX a cada 30s em `#board` (não troca no meio do drag)
- **Drag:** card inteiro (exceto botão recolher); `sort: false` — só muda de coluna/status; clique curto na placa ainda abre a OS
- **Recolher:** botão geral `data-cards-toggle-all` + por card `data-card-toggle`
- Preferência em `localStorage` (`kanban-cards-collapsed`, `kanban-card-overrides`)
- Recolhido: placa + seta na linha 1; veículo + ícones (▲ / ! / ⏱) na linha 2
- Expandido: OS numa faixa; tags Alta/Urgente/Atrasado em faixa própria (cabem 2+)

### 4.2 Entrada / OS nova

- Fluxo HTMX por placa: `workorders:plate_lookup` → veículo existente ou cadastro
- Criação: `create_service_order` em `services.py`
- URL: `/entrada/nova/`

### 4.3 Detalhe da OS / status

- Template com abas (progressive enhancement): Resumo, Serviços, Diagnóstico, Vistoria/fotos, Timeline, Histórico veículo, Saída
- Status do quadro: Aguardando avaliação → Em avaliação → Aguardando aprovação → Aguardando peça → Em manutenção → Finalizado
- Fechados: Entregue, Cancelado
- **Diagnóstico:** texto + fotos da categoria `DIAGNOSTICO` (galeria e upload na própria aba)
### 4.4 Serviços (ServiceTask)

- Status: PENDING / RUNNING / DONE / CANCELLED
- Ações HTMX: iniciar, concluir, reabrir, cancelar
- Partial: `templates/workorders/partials/_tasks.html`

### 4.5 Fotos

- `ServiceOrderPhoto` + categorias; soft-delete
- Campo `angle` (`PhotoAngle`): frente, traseira, laterais, diagonal, EXTRA
- `GUIDED_PHOTO_ANGLES` — 5 posições obrigatórias no app mobile
- Form: `PhotoUploadForm` + `MultipleFileField` (+ `angle` opcional)
- Limits: `MAX_UPLOAD_SIZE_MB`, extensões/MIME em settings
- Migração: `workorders.0004_photo_angle`

### 4.6 Vistoria

- `Inspection` 1:1 com OS · `InspectionItem` com condição (OK / Atenção / Avaria / Não verificado)
- Lista padrão `DEFAULT_INSPECTION_ITEMS` — rótulo copiado no item

### 4.7 Saída / entrega / assinatura

- Tela: `templates/workorders/delivery.html` + `static/js/signature.js`
- Campos opcionais: `received_by_name`, `received_by_document`, `delivery_signature`
- Assinatura: canvas → data URL PNG → validação Pillow no form
- Service: `deliver_vehicle`
- Migração: `workorders.0003_serviceorder_delivery_signature_and_more`

### 4.8 Cancelamento

- `cancel_service_order` — motivo obrigatório; só admin/recepção
- Não apaga histórico nem número

### 4.9 Clientes

- Model `Client`; telefone/CPF com `max_length` folgado para input formatado antes do normalize
- Forms em `apps/customers/forms.py`

### 4.10 Veículos / histórico

- Placa chave de entrada; `VehicleDetailView` com timeline de OS (tarefas + thumbs)
- Localizações: `VehicleLocation` (elevador, box…)
- **Cadastro rápido localização** nos forms (entrada/OS): recepção/admin → só nome (`apps/vehicles/services.py`)

### 4.11 Busca global

- URL `/buscar/` — placa, OS, cliente, telefone, modelo
- Resultados agrupados

### 4.12 Usuários / permissões

- `Role`: ADMINISTRADOR, RECEPCAO, MECANICO
- Capabilities: `can_register_entry`, `can_deliver_vehicle`, `can_cancel_order`, `can_delete_photos`, etc.
- **Cadastro rápido mecânico** (forms da OS): admin → nome + usuário + PIN 4 dígitos + telefone opcional (`apps/accounts/services.py`); recepção **só se** preferência em Configurações
- **Aba Configurações** (`/configuracoes/`): **admin only** — preferências, usuários/PINs, localizações

### 4.13 Auditoria

- `ActivityLog` + `EventType` + ícones
- Toda operação relevante chama `log_activity`

### 4.14 Layout / marca / mobile

- Tokens CSS: `--c-brand-red`, `--c-brand-navy`
- Navy = navegação/ações comuns; vermelho = atenção (Nova entrada, atraso, erro)
- **Nav superior** (`templates/partials/_header.html`) — sem sidebar; libera largura do Kanban
- **Atalho WhatsApp** no header (ícone): lista OS na oficina → `wa.me` (telefone/Zap do cliente). Busca por placa/nome/OS. Na página da OS, o cliente atual vem primeiro. *Não* é integração CRM/API.
- **Mobile:** barra inferior (`_mobile_nav.html`); header compacto (marca + avatar + sair)
- Mobile: Kanban por abas de coluna; OS por abas de seção
- Comentários Django multilinha: usar `{% comment %}` — `{# #}` em várias linhas **vaza** texto na UI

### 4.15 Testes / seed

```powershell
python -m pytest -q
python manage.py seed_demo --reset   # senha default oficina123
```

- Operações: `apps/workorders/test_operations.py`
- Template hygiene: `apps/core/tests.py` (`TemplateHygieneTests`)
- Seed cria usuários, clientes, veículos, OS em vários status, tarefas, vistorias

### 4.16 Settings / Postgres / deploy

- Settings: `config/settings.py` + `.env` (`python-dotenv`, `dj-database-url`)
- Postgres local portátil: `scripts/pg-start.ps1` / `pg-stop.ps1`
- Produção: Gunicorn `0.0.0.0:$PORT`, `DEBUG=False`, media em disco Render (`MEDIA_ROOT=/var/data/media`) via view autenticada `apps/core/media.py` (não depende de `static()` do DEBUG)
- Checklist: `check --deploy`, `collectstatic`, `migrate`
- **Deploy produção:** só com frase explícita + senha **`99738595`** na mesma mensagem (roteiro §0.3 — espelho Agro)
- **Domínio:** `drcentroautomotivo.com` (Hostinger) → apontar DNS para Render + custom domain no serviço web

#### Domínio `drcentroautomotivo.com` (Hostinger → Render)

1. Render → serviço **dr-centro-automotivo** → **Settings → Custom Domains** → adicionar `drcentroautomotivo.com` e `www.drcentroautomotivo.com`
2. Hostinger → DNS do domínio (substituir *dns-parking*):
   - **`www`** → CNAME → `dr-centro-automotivo.onrender.com`
   - **apex** (`@`) → CNAME/ALIAS para o host que o Render indicar *ou* redirecionar `@` → `www` (Hostinger tem atalho “Redirecionar domínio”)
3. Aguardar propagação (minutos a horas) · Render emite HTTPS automático
4. `render.yaml` já inclui hosts/CSRF; após sync Blueprint, redeploy
5. Testar login, upload de foto e Kanban em `https://drcentroautomotivo.com`

### 4.18 Configurações (`/configuracoes/`)

- **Somente administradores** (`can_manage_users`) — header, perfil mobile e todas as telas
- **Preferências:** toggle “Recepção pode cadastrar mecânicos” no cadastro rápido da OS (`WorkshopSettings`)
- **WhatsApp status (wa.me):** toggle “Avisar cliente ao mudar status” — abre WhatsApp com mensagem pronta (Kanban, detalhe, entrega). **Não** é API; operador confirma o envio
- **Usuários e PINs:** cadastro de administrador, recepção ou mecânico + redefinir PIN (4 dígitos) de qualquer usuário
- **Localizações:** lista + cadastro de pátio/box
- **Planilhas de cadastro:** modelo vazio, export dos cadastros atuais e import `.xlsx` (4 abas: localizações, clientes, veículos, usuários) — padrão Agro Consulta · `apps/core/spreadsheet/`
- **Dados de exemplo:** carregar pacote demo (OS em vários status) ou limpar com senha do admin logado · `is_demo` nos models · `demo_seed.py` / `demo_purge.py`
- Admin avançado → link `/admin/`
- Serviços: `apps/accounts/services.py` (`create_operational_user`, `set_user_pin`)

### 4.17 App mobile `/m/` (PWA)

- App: `apps/mobile/` · URLs sob `/m/` · CSS/JS `static/css/mobile.css`, `static/js/mobile.js`
- Fluxo: entrada (placa → cliente/KM/queixa) → vistoria → fotos
- OCR placa: foto → `POST /m/entrada/ler-placa/` → `platerec` (ONNX) no servidor; JS preenche `#m-plate` + HTMX lookup
  - Mercosul **e** antiga: EXIF, limiar de detecção mais baixo, contraste, rotações; I/L/O → dígito na 5ª posição (ex. `JKK2I88` → `JKK2188`)
  - Auto-preenche cliente/veículo **só do banco local** (já veio → lookup). API externa de placa = depois (roadmap).
- Fotos guiadas: 5 ângulos + extras (`PhotoAngle`) — UI mobile; **desktop:** vistoria guiada planejada, **sem** OCR de placa (Renan 31/08)
- Exemplos SVG: `static/mobile/shots/*.svg` — silhuetas por angulo (frente/traseira/laterais/diagonal), ASCII-only; cache `?v=` no `_photos.html`
- Checklist de portabilidade para o desktop: `oficina-roteiro.md` §8

---

## 5. Roadmap (ainda não)

Ordem sugerida quando Renan pedir (não implementar sem confirmação):

1. Storage de mídia em S3/R2 (antes de produção com fotos reais)
2. Orçamento / aprovação formal do cliente
3. Financeiro básico ligado à OS
4. Estoque / peças
5. WhatsApp / notificações
6. Agendamento
7. API externa de placa (marca/modelo/ano na 1ª visita) — adiado; hoje basta lookup local

---

## CHECKPOINT

### Versão / estado · 30/08/2026

- **Fases 1–13:** concluídas (núcleo operacional utilizável)
- **Testes:** suíte verde
- **Dev:** `http://127.0.0.1:8010/` · Postgres local
- **Revisão 30/08:** bugs alta→baixa corrigidos (P-004…P-012)
- **GitHub:** https://github.com/hinnen/DR-CENTRO-AUTOMOTIVO · branch `main`
- **Render:** ✅ **Live** · https://dr-centro-automotivo.onrender.com/ · `/healthz` ok (30/08 noite)
- **Custo estimado:** web Starter ~US$ 7 + Postgres Basic-256mb ~US$ 6 ≈ **US$ 13/mês**
- **Login demo:** só no **PC local** após `seed_demo` — user `admin` / senha `oficina123` (seed **bloqueado** em produção DEBUG=False)
- **Atenção fotos:** P-002 — media no disco Render some no restart; OK pra smoke; produção com fotos → S3/R2
- **Produção:** superuser criado no Shell Render (31/08)
- **Domínio:** `drcentroautomotivo.com` comprado Hostinger — DNS pendente (ver §4.16)

### WIP / recentes

| Data | O quê | Notas |
| ---- | ----- | ----- |
| 30/08 | Fix deploy: Pillow **10.4.0** (exigência `platerec`) | Build Render |
| 30/08 | `render.yaml` + `runtime.txt` + `/healthz` | Blueprint Oregon · não misturar SistVale |
| 30/08 | Docs `oficina.md` + `oficina-roteiro.md` + rule Cursor | Espelho do padrão banana do Agro |
| 30/08 | Dashboard: removeu “Painel operacional” + Nova entrada duplicada; Recolher cards nos filtros | menos desperdício de tela |
| 30/08 | Entrega: quem retirou + documento + assinatura canvas (opcionais) | migração `0003` · `signature.js` · testes `RetrievedByTests` |
| 30/08 | Marca vermelho/azul-escuro | CSS variables |
| 30/08 | Bug: comentário `{# #}` multilinha no `_order_card.html` vazava no Kanban | trocado por `{% comment %}` |
| 30/08 | PWA `/m/`: recepção + vistoria + perfil | `apps/mobile` · interligado à OS |
| 30/08 | OCR placa (Tesseract.js) + fotos guiadas 5 ângulos | `PhotoAngle` · migração `0004` · roteiro §8 |
| 30/08 | OCR placa migrado p/ servidor (`platerec` + onnxruntime) | `plate_ocr.py` · `entry_read_plate` · sem Tesseract.js |
| 30/08 | Fix SVG laterais quebrados (byte Latin-1 `à` no comentário) | `lateral_esq/dir.svg` · `mobile.css?v=9` |
| 30/08 | Redesign exemplos fotos guiadas (silhuetas limpas, sem placa fake) | `static/mobile/shots/*.svg` · `?v=2` · `mobile.css?v=11` |
| 30/08 | OCR: reforço placa antiga (EXIF, limiar ↓, contraste, rotações) | `plate_ocr.py` · Mercosul + antiga |
| 30/08 | Header: atalho WhatsApp (wa.me) — lista oficina + busca + prioridade da OS aberta | não é CRM/API · `whatsapp_picker` |
| 30/08 | Aba Diagnóstico: upload e galeria de fotos (categoria DIAGNOSTICO) | `detail.html` · `_photo_list.html` · âncora `#diagnostico` |
| 30/08 | Fix: fotos `/media/` 404 com DEBUG=False — view autenticada + disco Render | `apps/core/media.py` · `render.yaml` disk |
| 31/08 | Select + cadastrar: mecânico (admin, PIN 4) e localização (recepção/admin) nos forms da OS | `catalog_views.py` · `_creatable_select.html` |
| 31/08 | WhatsApp inline: botão wa.me na lista de clientes e no card expandido do Kanban | `_whatsapp_button.html` |
| 31/08 | Busca por placa: consulta só com 7 chars + menos queries no resumo | `build_plate_lookup_context` |
| 31/08 | OCR placa: resize no celular, passe rápido/lento no platerec, warmup no boot | `plate_ocr.py` · `mobile.js?v=9` |
| 31/08 | Aba Configurações: preferências, usuários+PINs, localizações (admin only) | `WorkshopSettings` · `/configuracoes/usuarios/` |
| 31/08 | Deploy produção: regra frase + senha `99738595` (espelho Agro) | `oficina-roteiro.md` §0.3 |
| 31/08 | WhatsApp status automático (wa.me): toggle em Preferências + abre ao mudar status | `status_whatsapp.py` · `WorkshopSettings` |
| 31/08 | Dados de exemplo + planilhas Excel (import/export cadastros) | `is_demo` · `/configuracoes/exemplos/` · `/configuracoes/planilhas/` · `openpyxl` |
| 31/08 | **Deploy prod 502** — investigar logs Render · rollback manual commit `341e099` no Dashboard se não voltar | código atual `8faf197` (reapply + lazy openpyxl + fix localização pk) |

**Rollback imediato:** Render Dashboard → **dr-centro-automotivo** → Deploys → redeploy do commit **`341e099`** (último live antes desta entrega). Git: `git revert 8faf197..8418d92` ou restaurar `main` em `341e099`.

**Rollback (31/08):** migrations desta entrega — `0002_is_demo` (accounts), `0003_is_demo` (customers/vehicles), `0005_is_demo` (workorders), `0001`/`0002` (core WorkshopSettings). Só relevantes se migrate rodou em prod.

### Pendências conhecidas

| ID | Item | Prioridade |
| -- | ---- | ---------- |
| P-001 | Cards Kanban calibrados p/ notebook 17–19" (248/72 px) — TV conferir depois | Baixa |
| P-002 | **Radar:** Media storage S3/R2 antes de volume alto de fotos (disco Render = piloto) | **Alta quando crescer volume** |
| P-003 | Auto-start do Postgres no Windows (hoje manual) | Baixa — Renan inicia com script |
| P-004 | Vistoria guiada (5 ângulos) no **desktop** — sem OCR de placa | Média — portar UI mobile |
| P-005 | DNS/domínio `drcentroautomotivo.com` → Render | Renan configura Hostinger |

### Instruções ao assistente (vivo)

- Novo chat → seguir `oficina-roteiro.md`
- Ao fechar entrega → atualizar este CHECKPOINT (o quê, arquivos-chave, teste OK?)
- Modelo de IA: Auto/Intelligence no dia a dia; Opus só em módulo novo, migração arriscada ou bug teimoso
- Não inventar módulo fora do escopo §0 do roteiro sem perguntar

---

## 6. Como o Renan usa o Cursor neste projeto

1. Abre chat novo
2. Anexa `@oficina-roteiro` (ou confia na rule) e descreve a tarefa
3. Assistente lê o roteiro → só os trechos necessários da `oficina.md`
4. Entrega código + atualiza CHECKPOINT
5. Renan testa no PC (`8010`)

Espelho do fluxo **banana / banana-roteiro** do Agro Consulta, com nomes do domínio da oficina.
