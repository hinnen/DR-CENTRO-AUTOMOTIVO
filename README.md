# DR Centro Automotivo

Sistema web de gestão operacional para oficina mecânica: controla o veículo da
chegada até a entrega — entrada, vistoria, ordem de serviço, mecânico
responsável, status, localização física, fotos e histórico por placa.

O diferencial buscado é objetivo: **em poucos segundos saber onde está cada
carro, quem está trabalhando nele, há quanto tempo está parado e o que falta
para terminar.**

> Esta versão cobre apenas o núcleo operacional. Financeiro, estoque, fiscal,
> orçamento, WhatsApp e agendamento ficam fora de escopo por decisão de projeto,
> mas a arquitetura foi pensada para recebê-los depois.

## Stack

- Python 3.13 · Django 6.1
- PostgreSQL (produção) · Django ORM
- Django Templates + HTMX + Alpine.js (apenas onde houver ganho real)
- CSS próprio com design tokens em CSS variables
- SortableJS no Kanban
- WhiteNoise para estáticos · Gunicorn em produção

Server-side first: JavaScript entra só onde melhora de fato a experiência.

## Pré-requisitos

- Python 3.13+
- PostgreSQL 14+ (18 em uso neste projeto)
- Git

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No Linux/macOS use `source .venv/bin/activate`.

## Variáveis de ambiente

Copie o exemplo e ajuste:

```powershell
Copy-Item .env.example .env
```

Gere uma `SECRET_KEY`:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

| Variável | Descrição |
| --- | --- |
| `SECRET_KEY` | Obrigatória. Com `DEBUG=False` a aplicação recusa iniciar sem ela. |
| `DEBUG` | `True` só em desenvolvimento. |
| `ALLOWED_HOSTS` | Domínios liberados, separados por vírgula. |
| `CSRF_TRUSTED_ORIGINS` | Origens https confiáveis, separadas por vírgula. |
| `DATABASE_URL` | Conexão do banco. Sem ela, cai em SQLite local. |
| `WORKSHOP_NAME` | Nome exibido no layout. |
| `MEDIA_ROOT` | Destino das fotos. |
| `MAX_UPLOAD_SIZE_MB` | Tamanho máximo por foto. |
| `USE_MANIFEST_STATIC` | `True` em produção, após `collectstatic`. |

## Banco de dados

O projeto usa **PostgreSQL 18**. Crie o banco e o usuário:

```sql
CREATE ROLE oficina WITH LOGIN PASSWORD 'sua-senha' CREATEDB;
CREATE DATABASE oficina OWNER oficina ENCODING 'UTF8';
```

E aponte no `.env`:

```
DATABASE_URL=postgres://oficina:sua-senha@127.0.0.1:5432/oficina
```

**Sobre o SQLite:** o projeto cai em SQLite apenas quando `DATABASE_URL` está
ausente, para não travar quem acabou de clonar o repositório. Não é o banco do
projeto — desenvolvimento, homologação e produção usam PostgreSQL.

### Instalação local desta máquina

O PostgreSQL foi instalado a partir dos binários portáteis da EDB em
`C:\Users\RenanHinnen\pgsql`, porque a conta do Windows não tem privilégio de
administrador. A consequência prática: **ele não roda como serviço e precisa ser
iniciado manualmente depois de cada reinicialização.**

```powershell
.\scripts\pg-start.ps1   # inicia (não faz nada se já estiver no ar)
.\scripts\pg-stop.ps1    # para
```

Os scripts assumem `C:\Users\RenanHinnen\pgsql`; em outra máquina, defina a
variável de ambiente `PGHOME` apontando para a pasta do PostgreSQL.

O cluster foi criado com encoding UTF-8 e collation ICU `pt-BR`, e as conexões
TCP exigem senha (`scram-sha-256`).

Para abrir um console SQL:

```powershell
$env:PGPASSWORD = "sua-senha"
C:\Users\RenanHinnen\pgsql\bin\psql.exe -h 127.0.0.1 -U oficina -d oficina
```

## Migrations e primeiro acesso

```powershell
.\scripts\pg-start.ps1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8010
```

A aplicação sobe em <http://127.0.0.1:8010/> e o admin em `/admin/`.

> **Porta 8010, não 8000.** Nesta máquina a porta 8000 já é usada por outro
> projeto Django. Rodar os dois na mesma porta faz um deles falhar ao subir e o
> outro receber requisições que não são dele.

## Dados de demonstração

```powershell
python manage.py seed_demo
```

Cria administrador, mecânicos, clientes, veículos, localizações e ordens de
serviço distribuídas pelos status, o suficiente para testar o Kanban.
Nunca deve ser executado em produção.

Use `--reset` para apagar os dados operacionais antes de recriar, e
`--password` para trocar a senha padrão (`oficina123`):

```powershell
python manage.py seed_demo --reset --password minhasenha
```

## Testes

```powershell
python -m pytest
```

Cobrem as regras que não podem quebrar em silêncio: normalização e duplicidade
de placa, sequência de OS, transições de status e o histórico correspondente,
progresso de serviços, validação de upload, checklist da vistoria, KM de saída
menor que o de entrada, assinatura da retirada, cancelamento, permissão por
perfil, veículo entregue saindo do Kanban, atrasos e busca por placa.

## Perfis de acesso

| Perfil | O que faz |
| --- | --- |
| **Administrador** | Acesso completo, incluindo usuários, exclusões e configurações. |
| **Recepção** | Clientes, veículos, entradas, OS, status, serviços, fotos, vistoria, histórico, saída e cancelamento. |
| **Mecânico** | Consulta veículos e OS, registra diagnóstico e observações, envia fotos, faz vistoria, adiciona e conclui serviços e move as etapas do quadro. |

O mecânico **não** cadastra ou exclui clientes, não remove fotos, não registra
saída, não cancela OS e não administra usuários.

As permissões vivem em properties do model `User` e são validadas no backend
via `RoleRequiredMixin` e `capability_required`. O template pode esconder um
botão, mas nunca é a fonte da autorização.

## Estrutura do projeto

```
config/                 settings, urls, wsgi/asgi
apps/
  core/                 bases de model, permissões, context processors, páginas de erro
  accounts/             User customizado, login/logout, perfil
  customers/            clientes
  vehicles/             veículos e localizações
  workorders/           ordens de serviço, status, tarefas, vistoria, fotos
  dashboard/            painel operacional e Kanban
  mobile/               PWA de vistoria no celular (`/m/`)
templates/              templates globais e partials reutilizáveis
static/                 CSS e JS próprios (inclui `css/mobile.css` e `mobile/`)
static/vendor/          HTMX e SortableJS servidos localmente, sem CDN
media/                  uploads em desenvolvimento
scripts/                utilitários de ambiente (start/stop do PostgreSQL)
```

## App de vistoria no celular (PWA)

Há um aplicativo web separado em `/m/`, feito para instalar na tela inicial do
celular e fazer o **primeiro contato** no pátio: abrir a entrada (cliente,
telefone/WhatsApp, veículo, KM, queixa), registrar a vistoria e tirar fotos.
Usa o **mesmo login e os mesmos dados** do sistema do computador — o restante
(mecânico, localização, serviços, status) continua no notebook.

### Fluxo no celular

1. **Nova entrada** → digite a placa.
2. Carro conhecido: confirme telefone, KM e queixa → OS aberta.
3. Placa nova: cadastre nome, telefone, marca/modelo → OS aberta.
4. Em seguida faça a **vistoria** e as fotos.
5. No computador, complete mecânico, status, serviços etc.

### Instalar no celular

- **Android (Chrome):** abra `/m/` → menu ⋮ → **Instalar aplicativo** (ou
  **Adicionar à tela inicial**).
- **iPhone (Safari):** abra `/m/` → Compartilhar → **Adicionar à Tela de Início**.

Em produção a instalação completa (PWA) exige **HTTPS**. Em `localhost` o
Chrome também permite instalar.

## Deploy

Checklist antes de publicar:

```powershell
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py migrate
```

No `.env` de produção: `DEBUG=False`, `SECRET_KEY` própria, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` do PostgreSQL e `USE_MANIFEST_STATIC=True`.

Servir com Gunicorn, nunca com `runserver`:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Com `DEBUG=False` o projeto já ativa HSTS, cookies seguros, redirect HTTPS e
`SECURE_PROXY_SSL_HEADER` quando atrás de proxy.

## Armazenamento de mídia

As fotos usam `ImageField` sobre a abstração de storage do Django — nunca acesso
direto ao filesystem. Em desenvolvimento gravam em `MEDIA_ROOT`.

Em produção, **não use o disco do servidor**: filesystem de plataformas como
Render é efêmero e as fotos somem a cada deploy. Configure um storage externo
(S3, Cloudflare R2, Backblaze) trocando apenas a chave `default` de `STORAGES`.

## Regras de negócio já implementadas

**Placa é a chave de entrada.** Ela é normalizada (maiúsculas, sem hífen nem
espaço) antes de gravar e antes de buscar, então `abc-1d23`, `ABC 1D23` e
`ABC1D23` encontram o mesmo carro. São aceitos o padrão antigo e o Mercosul.

**Telefone também é normalizado**, só dígitos e sem o `+55` redundante. É isso
que permite avisar a recepção quando ela está prestes a cadastrar um cliente
que já existe.

**Numeração de OS nunca se repete.** O próximo número sai de um contador
travado com `SELECT FOR UPDATE`, então dois atendimentos simultâneos não pegam
o mesmo número. Cancelar uma OS não devolve o número para a fila.

**Toda mudança de status deixa rastro.** `transition_service_order_status`
grava quem mudou, quando, de onde para onde e a observação, dentro da mesma
transação da mudança. Não existe caminho na aplicação que altere o status sem
passar por ela.

**Entrega e cancelamento não entram pelo Kanban.** Os dois exigem dados
próprios (KM de saída, motivo), então o quadro só move entre os seis status
operacionais. Uma OS entregue ou cancelada não aceita mais mudanças.

**Tempo não é gravado, é calculado.** "Na oficina" vem da data de entrada e
"neste status" vem do histórico. Assim nunca há um contador desatualizado
contradizendo a linha do tempo.

**O arrastar-e-soltar não decide nada.** O navegador pede a mudança, o backend
relê o status atual com trava e valida. Se recusar, responde `409` e o card
volta sozinho para a coluna de origem — o que evita duas pessoas mexendo ao
mesmo tempo deixarem a tela mentindo.

**Serviços são linhas, não um parágrafo.** Cada `ServiceTask` é concluída
individualmente e tem responsável próprio, o que dá o "2 de 3 concluídos" do
card e prepara a medição de produtividade por mecânico. Serviço cancelado sai
do denominador: contá-lo faria o progresso nunca fechar.

**Foto não é apagada, é marcada como removida.** A exclusão é lógica e guarda
quem removeu e quando. Foto de entrada é a prova do estado em que o carro
chegou, e o upload nunca sobrescreve um arquivo anterior: o nome no storage é
um UUID, não o nome que veio do celular.

**Upload é validado três vezes no servidor.** Extensão, MIME e abertura real
pelo Pillow. O `accept` do input é só uma sugestão ao navegador — um cliente
qualquer pode enviar outra coisa.

**KM de saída menor que o de entrada não é bloqueado, é justificado.** Erro de
digitação na chegada e troca de painel acontecem de verdade; bloquear levaria
o balcão a inventar um número. Sem justificativa a entrega não passa, e o
texto fica registrado na OS.

**Finalizado e entregue são coisas diferentes.** Finalizado significa serviço
pronto com o carro ainda na oficina. Só a entrega tira o veículo do quadro.

**Quem retirou o veículo é registro opcional.** Nome, documento e assinatura de
quem levou o carro ficam em campos separados do cliente, porque com frequência
é o filho, o motorista ou o funcionário da empresa. Nenhum é obrigatório: o
cliente costuma estar com pressa no balcão, e campo obrigatório aqui viraria
`...` digitado só para o formulário passar. Quando preenchido, o nome aparece na
linha do tempo e a assinatura fica anexada à OS como PNG. A assinatura é
desenhada em `<canvas>` e chega como data URL — o servidor decodifica, confere
o tamanho e abre pelo Pillow antes de gravar.

**OS não é apagada.** Cancelar exige motivo e preserva o histórico inteiro,
inclusive o número, que continua queimado.

**O checklist da vistoria copia o rótulo para cada item.** Mudar a lista padrão
amanhã não reescreve o que foi vistoriado ontem — e um `InspectionTemplate`
futuro só precisa alimentar pares (chave, rótulo) diferentes, sem migração de
dados.

**Tudo que importa vai para o `ActivityLog`.** Criação, status, mecânico,
previsão, localização, diagnóstico, serviços, fotos, vistoria, finalização,
entrega e cancelamento — sempre com autor e data/hora. É a fonte da linha do
tempo, e no admin é somente leitura: auditoria que pode ser editada não serve
de auditoria.

## Decisões de interface

**Cores da marca.** O vermelho (`#a31b33`) e o azul-escuro (`#152e69`) foram
amostrados da fachada e do logotipo. Na tela o azul conduz a navegação e as
ações comuns, e o vermelho fica reservado para o que pede ação ou atenção:
o "+ Nova entrada", o atraso e o erro. Grandes superfícies vermelhas cansam
quem passa o dia no sistema, e um vermelho usado em tudo deixaria de sinalizar
qualquer coisa. Tudo sai de CSS variables em `static/css/app.css`.

**Cor nunca aparece sozinha.** Status, condição de vistoria e atraso sempre têm
rótulo escrito junto — o pátio tem sol forte e nem todo mundo distingue verde
de vermelho.

**As abas da OS são progressive enhancement.** O servidor manda todas as seções
visíveis e empilhadas; o JavaScript apenas passa a mostrar uma por vez. Se o
script falhar, a página continua completa, e um link para `#fotos` abre a aba
que contém aquela âncora.

**No celular o Kanban vira uma coluna por vez.** Arrastar card em tela pequena
é impraticável, então lá a mudança de status é feita pela tela da OS. Acima de
1024px as abas de coluna somem e o arrastar-e-soltar volta.

## Fases de implementação

| Fase | Escopo | Status |
| --- | --- | --- |
| 1 | Fundação: Django, PostgreSQL, settings, Custom User, layout, auth | Concluída |
| 2 | Clientes e veículos | Concluída |
| 3 | Entrada e ordem de serviço | Concluída |
| 4 | Status e histórico de status | Concluída |
| 5 | Dashboard e Kanban | Concluída |
| 6 | Serviços da OS | Concluída |
| 7 | Fotos e vistoria | Concluída |
| 8 | Histórico por placa e busca global | Concluída |
| 9 | Saída, entrega e cancelamento | Concluída |
| 10 | Permissões e auditoria | Concluída |
| 11 | Responsividade e UX | Concluída |
| 12 | Testes | Concluída |
| 13 | README e produção | Concluída |
