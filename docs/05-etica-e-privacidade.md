# 05 — Ética e privacidade

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b></sub>

---

Este projeto mede o rádio de terceiros sem que eles saibam. Isso não é um detalhe: é a
característica que define a tecnologia. Vale pensar nisso **antes** de coletar, não depois.

## O que o projeto inevitavelmente captura

Ao varrer o ambiente, você coleta:

- **BSSIDs** (endereços MAC de roteadores) de vizinhos. MAC é **dado pessoal** sob a LGPD:
  identifica um equipamento e, por consequência, um domicílio. Bases como a WiGLE mapeiam
  BSSID → coordenada geográfica.
- **SSIDs**, que frequentemente contêm nome de família, apartamento ou empresa.
- Indiretamente, **padrões de ocupação** dos vizinhos — se um AP oscila, alguém se moveu perto dele.

## Decisões já embutidas no código

| Decisão | Onde | Por quê |
|---|---|---|
| BSSID vira hash SHA-256 truncado, com salt | `src/survey.py` | Mantém o AP identificável entre execuções, sem guardar o MAC |
| SSID **nunca** é gravado | `src/survey.py` | É o campo com maior chance de conter nome de pessoa |
| `--keep-bssid` existe, mas é opt-in | `src/survey.py` | Só para identificar os **seus** APs, em base local |
| `data/raw/` no `.gitignore` | `.gitignore` | Medições não sobem para lugar nenhum por acidente |

## Regras para este projeto

1. **Mapeie só o seu espaço.** Reconstruir a planta baixa da casa do vizinho não é curiosidade
   técnica — é vigilância, e provavelmente ilegal.
2. **Avise quem mora com você.** Uma pessoa consegue perceber uma câmera; ninguém percebe um
   laptop fazendo tomografia. Isso é justamente o problema.
3. **Nunca publique dados brutos.** Um `survey.jsonl` com BSSIDs reais é, na prática, um
   mapa de rede da sua vizinhança. Publique mapas e código; jamais medições cruas.
4. **Não capture payload.** No modo monitor (fase 4), grave apenas frames de gerenciamento e
   beamforming. Interceptar conteúdo de comunicação alheia é crime, mesmo criptografado.
5. **Apague o que não usar.** Dado que não existe não vaza.

## O ponto cego que a literatura levanta

O MIT Technology Review coloca o problema com precisão: as características físicas das ondas
**não podem ser criptografadas** como dados tradicionais. Daí decorre que "alguém sentado do
lado de fora de sua casa poderia obter informações sobre em que cômodo as pessoas estão" — e
que, diferentemente de câmeras, "não há como saber se as lâmpadas automatizadas de alguém estão
te monitorando".

E há uma lacuna reconhecida na padronização: existe uma área em que o IEEE não está
trabalhando, ao menos não diretamente — **privacidade e segurança** do sensing.

Some a isso o **WhoFi** (La Sapienza), que reidentifica indivíduos por assinatura de CSI com
95,5% de acurácia, e o BFI que, por especificação, **trafega em texto claro antes da
criptografia**. A conclusão é desconfortável e correta: **o Wi-Fi vaza informação física sobre
o ambiente e sobre quem está nele, e não há mecanismo previsto para impedir isso.**

Fazer este projeto é, entre outras coisas, uma forma de entender concretamente esse risco.
Vale fazê-lo com a postura de quem estuda uma vulnerabilidade — não de quem a explora.

## Se for publicar

- Publique **código e mapas**, nunca `data/raw/`.
- Anonimize a planta (não indique endereço, andar ou número do apartamento).
- Deixe explícito no repositório que a coleta foi feita **no próprio domicílio, com
  consentimento dos moradores**.
- Respeite as regras da empresa ao compartilhar qualquer material derivado deste estudo com
  terceiros.
