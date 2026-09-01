# OFICINA — DR Centro Automotivo (anexe com `@oficina`)

Sistema web de gestão **operacional** da oficina mecânica **DR Centro Automotivo**.
Controla o veículo da chegada até a entrega.

**Este é o anexo de contexto vivo do projeto.** Leitura guiada: **`oficina-roteiro.md`**
(ler **antes** deste arquivo). A rule Cursor em `.cursor/rules/dr-centro-automotivo.mdc`
puxa o roteiro automaticamente.

| Você quer… | Faça |
| ---------- | ---- |
| Retomar trabalho / novo chat | `@oficina-roteiro` (ou só descrever a tarefa) |
| Detalhe fino / histórico / WIP | `@oficina` + grep `CHECKLIST ÚNICO` |
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
| **Testes** | `pytest` · **251 OK** (31/08/2026) |
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
- Placa nova: **buscar cliente cadastrado** (nome/telefone) antes de criar outro — desktop (`/clientes/buscar/`) e mobile (etapa 1 do wizard)
- HTMX mobile: input `#m-client-search` deve enviar parâmetro **`q`** (igual desktop); nome errado (`client_search_q`) quebrava a busca — corrigido 01/09 noite
- Um cliente pode ter **vários veículos**; `Vehicle.client` é FK (não 1:1)
- Placa: `normalize_plate` ignora traço/espaço (ABC-1234 = ABC1234); antiga e Mercosul
- Campo grande na etapa 1; JS formata digitação; sem cadastro → CTA **Cadastrar novo veículo**
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
- **Cadastro rápido mecânico** (forms da OS): admin → nome + usuário + PIN 4 dígitos + telefone opcional (`apps/accounts/services.py`)
- **Hub Configurações** (`/configuracoes/`) — só admin: preferências (`WorkshopSettings`), usuários/PINs, localizações, dados de exemplo, planilhas Excel

### 4.18 Configurações / exemplos / planilhas

- URLs: `apps/core/urls.py` · views `settings_views.py` · forms `settings_forms.py`
- **Preferências:** recepção pode cadastrar mecânico; aviso WhatsApp ao mudar status (opcional)
- **Dados de exemplo:** `demo_seed.py` / `demo_purge.py` · flag `is_demo` em User, Client, Vehicle, ServiceOrder
- **Planilhas:** `apps/core/spreadsheet/` · `openpyxl` · import/export clientes, veículos, usuários, localizações
- **Produção segura:** OCR placa **fora do boot** (lazy); `/healthz` via `HealthCheckMiddleware`

### 4.13 Auditoria

- `ActivityLog` + `EventType` + ícones
- Toda operação relevante chama `log_activity`

### 4.14 Layout / marca / mobile

- Tokens CSS: `--c-brand-red`, `--c-brand-navy`
- Navy = navegação/ações comuns; vermelho = atenção (Nova entrada, atraso, erro)
- **Nav superior** (`templates/partials/_header.html`) — sem sidebar; libera largura do Kanban
- **Versão do sistema:** top bar desktop + `/m/` · `APP_VERSION` (default `0.0.1`) · ex.: **V: 0.0.1**
- **Atalho WhatsApp** no header (ícone): lista OS na oficina → `wa.me` (telefone/Zap do cliente). Busca por placa/nome/OS. Na página da OS, o cliente atual vem primeiro. *Não* é integração CRM/API.
- **Mobile:** barra inferior (`_mobile_nav.html`); header compacto (marca + avatar + sair)
- **Reportar bug (global):** botão 🐞 canto inferior direito · Alt+B · desktop + `/m/` (logado)
  - JS: `static/js/bug_report.js` · API `POST /api/bug-report/` · print automático (html2canvas)
  - Lista admin: `Configurações → Bugs reportados` · detalhe com **Copiar prompt Cursor** (`@oficina-roteiro`)
  - Model: `apps/core/models.py` · `BugReport` · migrate `core.0003`
  - E-mail opcional: env `BUG_REPORT_EMAIL` (SMTP configurado)
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
- Preview WhatsApp/Facebook: `SocialPreviewMiddleware` responde `/` com HTML OG (200) para bots; `PUBLIC_BASE_URL` + `OG_IMAGE_VERSION` no `render.yaml`
- Checklist: `check --deploy`, `collectstatic`, `migrate` (incl. `core.0003` bug report)

### 4.17 App mobile `/m/` (PWA)

- App: `apps/mobile/` · URLs sob `/m/` · CSS/JS `static/css/mobile.css`, `static/js/mobile.js`
- **Link WhatsApp / instalar:** `https://drcentroautomotivo.com/m/instalar/` (público) — card central estilo Agro Ajuste; Chrome → Instalar; iOS → Compartilhar → Tela de Início
- **Sistema no PC:** `https://drcentroautomotivo.com/` (Kanban / OS)
- **App no celular:** `/m/` (login) após instalar ou “Continuar no navegador”
- Fluxo: entrada (placa → **wizard**: cliente → queixa/KM → veículo) → vistoria → fotos
  - Placa nova: **buscar cliente cadastrado** na etapa 1 (nome/telefone) — vincula 2º+ carro ao mesmo dono
  - Cadastro novo: 3 telas; retorno (placa conhecida): 2 telas — campos maiores; opcionais em “mais opções”
  - Continuar / Voltar + Enter avança; no fim “Abrir OS e ir à vistoria”
  - Nome + telefone obrigatórios; queixa em destaque; quem trouxe (opcional); Normal/Urgente
  - Campo OS: `brought_by_name` (quem deixou o carro no pátio)
- OCR placa: foto → `POST /m/entrada/ler-placa/` → `platerec` **lazy**; mantém modelo em memória (`PLATE_OCR_KEEP_LOADED=1`) para 2ª+ foto rápida; JS resize **800**
  - Ao abrir `/m/entrada/`: `POST /m/entrada/aquecer-ocr/` pré-carrega o modelo (não no boot — evita 502)
  - Env: `ENABLE_PLATE_OCR=1` · `PLATE_OCR_WARMUP=0` · `PLATE_OCR_KEEP_LOADED=1` · `PLATE_OCR_MAX_SIDE=800` · `PLATE_OCR_THREADS=2`
  - Mercosul: 5ª posição **sempre letra** (I≠1); empate I/1 pede confirmação do usuário
  - Auto-preenche a placa só com confiança ≥ ~99% e sem ambiguidade; senão pede **Confirmar / Corrigir**
  - Auto-preenche cliente/veículo **só do banco local** (já veio → lookup). API externa de placa = depois (roadmap).
- Fotos guiadas: 5 ângulos + extras (`PhotoAngle`) — UI só no mobile por enquanto
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

## CHECKLIST ÚNICO · 01/09/2026

**Produção Live:** verificar pós-deploy · https://drcentroautomotivo.com/

### PACOTE PRONTO (falta subir · senha 99738595)

| P | Item | Status | Verificação |
| - | ---- | ------ | ----------- |
| **P0** | Fix busca cliente **mobile** (`name="q"`) | **Pronto para envio à produção** | 38 testes · HTTP smoke local (admin/9973) · nome + telefone → **Usar** |
| **P2** | Versão top bar `V: 0.0.1` | **Pronto para envio à produção** | sem migrate |

| P | Item | Status |
| - | ---- | ------ |
| **P0/P1** | 502 · config · OCR · wizard · bug report · busca desktop | ✅ **Enviado** |
| **P2** | Media S3/R2 · fotos desktop | **Pendente** |
| **P3** | Financeiro · estoque · CRM · agendamento · fiscal | **Pendente** |

### Checkpoint Live

| | |
| - | - |
| Rollback | `d888d80` · `rollback/pre-mobile-search-fix-20260901` |
| Doc | `docs/ROLLBACK-MOBILE-SEARCH-FIX-20260901.md` |
| Smoke pós-deploy | `/healthz` · `/m/entrada/novo/` → buscar nome/telefone → **Usar** → 2º carro mesmo cliente |

### Deploy (lojas abertas — pausar antes)

1. Pausar vendas · *«pode subir para produção»* + senha **`99738595`**
2. Smoke 2 min (busca mobile + versão na top bar)
3. OK → marcar **Enviado** · falhou → rollback `rollback/pre-mobile-search-fix-20260901`

---

## 6. Como o Renan usa o Cursor neste projeto

1. Abre chat novo
2. Anexa `@oficina-roteiro` (ou confia na rule) e descreve a tarefa
3. Assistente lê o roteiro → só os trechos necessários da `oficina.md`
4. Entrega código + atualiza CHECKLIST ÚNICO
5. Renan testa no PC (`8010`)

Espelho do fluxo **banana / banana-roteiro** do Agro Consulta, com nomes do domínio da oficina.
