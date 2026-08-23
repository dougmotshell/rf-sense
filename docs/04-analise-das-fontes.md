# 04 — Análise crítica das fontes

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b></sub>

---

Fontes trazidas para o projeto, avaliadas contra a pergunta real: **isso reconstrói a geometria
do ambiente, e roda no meu hardware?**

---

## 4.1 RuView / WiFi-DensePose

**O que promete:** "transforma sinais de Wi-Fi comuns em estimativa de pose humana em tempo
real, sinais vitais e detecção de presença — sem um único pixel de vídeo".

**O que realmente exige:** a própria documentação do projeto diz que é preciso **hardware capaz
de CSI (ESP32-S3 ou NIC de pesquisa)**. Laptops de consumo, segundo o próprio projeto,
"conseguem apenas detecção de presença baseada em RSSI, que é significativamente menos capaz".

**O que o projeto admite sobre si mesmo:**
- Acurácia de pose sem câmera: **PCK@20 ≈ 2,5%** com labels proxy — contra uma meta de 35%+
  com ground truth de câmera. Ou seja: hoje, essencialmente não funciona para pose.
- As fases de coleta de dados e avaliação **ainda estão pendentes**.

**Ceticismo da comunidade:** há quem chame o projeto de falso. A avaliação equilibrada da
CNX Software: a ciência de base é real (a Espressif demonstrou CSI em ESP32 já em 2022), é
provável que várias alegações sejam exageradas ou válidas só em condições muito específicas,
mas nada indica que o projeto seja inteiramente inútil. Notavelmente, **não existe demo em
vídeo do RuView** — só pessoas falando sobre ele.

**Relevância para nós:** 🔴 baixa. Detecta **pessoas**, não reconstrói **ambiente**, e não roda
no QCA6174. Serve como leitura de arquitetura, não como base de código.

---

## 4.2 WhoFi — Universidade La Sapienza (Roma)

**O que faz:** identifica **quem** é a pessoa através de paredes, usando a assinatura que o
corpo imprime no **CSI** como se fosse uma biometria. Reporta até **95,5% de acurácia**,
superando o EyeFi (75%).

**Relevância para nós:** 🔴 baixa para o objetivo, 🟡 alta como alerta de privacidade.
É reidentificação de pessoas, não mapeamento. Usa CSI. Mas mostra o quanto o canal Wi-Fi
carrega informação sobre quem está no ambiente — o que reforça `docs/05`.

---

## 4.3 MIT Technology Review Brasil — "Como o Wi-Fi sensing se tornou uma tecnologia funcional"

A fonte mais útil das quatro, porque é a mais honesta sobre limites.

**O que confirma:**
- A tecnologia **já está em produção** em milhões de casas, via provedores de internet
  (Origin Wireless/Hex Home, Cognitive Systems, Sengled, Google Nest Hub, roteadores Fios).
- O padrão **802.11bf** (WLAN Sensing) vem sendo trabalhado desde 2020 e vai tornar o CSI
  mais consistente entre fabricantes.
- Não exige equipamento dedicado: lâmpadas, tomadas e alto-falantes inteligentes já conectados
  "podem instantaneamente se tornar sensores".

**O dado que decide o nosso escopo** — sobre resolução:

> Ondas de Wi-Fi (**5–12 cm**) cobrem grandes áreas, mas com **menor precisão que radar (5 mm)**.

É a confirmação numérica do que `docs/01` argumenta: o comprimento de onda do Wi-Fi limita
fisicamente o detalhe. Você mapeia **paredes**, não **objetos**.

**Onde a indústria realmente chegou:** presença (descrita como ~100%), rastreamento de
movimentação, automação de luz. Respiração, queda, marcha e identificação continuam em
**pesquisa**. E ninguém no mercado vende **reconstrução de planta baixa por Wi-Fi** — o que é
um sinal: se fosse fácil, já estaria em produto.

**Sobre confiabilidade**, cita Sam Yang: "o sinal não está livre de interferências"; e conclui
que "à medida que o Wi-Fi sensing aumenta seu nível de levantamento de dados, a confiabilidade
desses detalhes permanece incerta".

**Relevância:** 🟢 alta como calibrador de expectativa e como fonte sobre 802.11bf.

---

## 4.4 O que as manchetes fazem

Existe um padrão consistente nas três matérias de divulgação:

| A manchete diz | O paper faz |
|---|---|
| "Enxergar através das paredes" | Classificar movimento/identidade a partir de perturbação de canal |
| "Visão 3D com Wi-Fi" | Estimar pose 2D em ambiente de treino controlado |
| "Sem câmeras" | Treinado **com** câmeras, que geram o ground truth |

Isso não é fraude — é jornalismo científico comprimindo nuance. Mas para quem vai *construir*,
a nuance é o projeto inteiro.

---

## 4.5 As fontes que realmente importam para este projeto

Ironicamente, nenhuma das mais divulgadas. As relevantes são:

1. **Holl & Reinhard, "Holography of Wi-Fi Radiation"** (PRL 118, 183901, 2017) — prova que
   imageamento 3D com Wi-Fi é fisicamente possível, e revela exatamente o requisito que nos
   bloqueia: gravação **fase-coerente** com antena de referência fixa + antena móvel.
2. **"Structure from WiFi (SfW)"** (arXiv 2403.02235, ACC 2024) e **"Inverse k-visibility"**
   (*Autonomous Robots*, 2026) — mapeamento **geométrico** de interiores usando **só RSSI**.
   É o trabalho mais alinhado ao objetivo *e* ao hardware disponível.
3. **Wi-BFI** (arXiv 2309.04408) — extração de beamforming feedback de dispositivos comerciais,
   sem modificar firmware. O caminho para informação angular.
4. **BatMapper** (MobiCom/IMWUT) — reconstrução de planta baixa com o **microfone e alto-falante
   do celular**. Não é RF, mas é custo zero e produz o **ground truth** métrico que valida o
   mapa de RF. Ver `docs/03`, fase 4.

Referências completas em `docs/06-referencias.md`.
