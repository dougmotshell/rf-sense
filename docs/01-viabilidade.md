# 01 — Viabilidade: dá para "enxergar" o ambiente com Wi-Fi?

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b> · Pesquisa: 2026-08-23</sub>

---

## 1. O divisor de águas: fase

Toda técnica de imageamento por ondas — radar, ultrassom, tomografia, holografia — depende de
saber **quando** a onda chegou, não só **quanta** energia chegou. Isso é a **fase**.

- **Com fase**, você pode combinar coerentemente medições feitas em posições diferentes e
  formar uma **abertura sintética**. Resolução vai a centímetros. É SAR, é holografia.
- **Sem fase**, você tem apenas potência. Não dá para focar. Sobra resolver um problema
  inverso de **atenuação**: "o sinal que atravessou esta linha perdeu 12 dB a mais do que o
  esperado, logo há algo denso no caminho". Resolução vai a **metros**. É tomografia.

Essa única distinção decide tudo no seu projeto.

## 2. Prova de que a coisa funciona: holografia de Wi-Fi (TUM, 2017)

Holl & Reinhard, publicado na *Physical Review Letters*, é a referência canônica para
"enxergar o ambiente com Wi-Fi":

> Sistemas de transmissão sem fio como Wi-Fi ou Bluetooth emitem **luz coerente** — ondas
> eletromagnéticas com amplitude e fase precisamente conhecidas. Ao se propagar no espaço,
> essa radiação forma um **holograma**: uma frente de onda 2D que codifica uma visão 3D de
> todos os objetos atravessados.

O método deles: tratar a frente de onda como holograma e aplicar as mesmas matemáticas de
imageamento holográfico e de **SAR**. O hardware é enganosamente simples —
**uma antena fixa e uma antena móvel**. A antena fixa serve de **referência de fase**; a móvel
varre uma região de ~1 m gravando o campo de forma **fase-coerente**. Com isso reconstroem
vistas 3D de objetos e emissores.

O achado bonito do paper: a banda estreita do Wi-Fi doméstico (2,4 e 5 GHz) **é suficiente** —
porque a resolução vem da abertura sintética, não da largura de banda.

**Por que você não pode reproduzir:** "gravar de forma fase-coerente" é justamente o que uma
NIC comum não deixa fazer. Isso exige SDR (HackRF, USRP) ou CSI com fase calibrada. Sem isso,
não existe holografia. Este é o muro do projeto, e ele é intransponível a custo zero.

## 3. Onde o seu hardware bate no muro

| Camada de sinal | Tem fase? | Acesso no QCA6174 (`ath10k`) |
|---|---|---|
| **RSSI** — potência agregada | ❌ | ✅ trivial (`nmcli`), sem root |
| **Spectral scan** — bins de FFT do baseband | ❌ (magnitude) | ✅ kernel compilado com `CONFIG_ATH10K_SPECTRAL=y` |
| **BFI** — ângulos de beamforming | 🟡 informação **angular**, fase comprimida | ✅ via modo monitor (trafega em texto claro) |
| **CSI** — amplitude + fase por subportadora | ✅ | ❌ **indisponível** — Atheros CSI Tool é só `ath9k` |
| **IQ bruto** — o sinal em si | ✅ | ❌ exige SDR |

O `ath10k` não tem ferramenta de CSI utilizável: o firmware da Qualcomm só reporta CSI em
*sounding packets*, e nunca surgiu tool madura. As plataformas que funcionam são **Atheros CSI
Tool** (`ath9k`), **Intel 5300 CSITool**, **Nexmon** (Broadcom/Cypress), **ESP32 CSI Toolkit** e
**PicoScenes** (Intel AX210/AX200, QCA9300, IWL5300 + SDRs). Nenhuma cobre o QCA6174.

**Consequência:** holografia e SAR estão fora. Ponto final. Qualquer plano que dependa deles é
fantasia, e é melhor saber isso agora do que depois de três meses de código.

## 4. O que sobra — e é mais interessante do que parece

### 4.1 Tomografia por atenuação (o caminho principal) ⭐

A ideia, emprestada da tomografia de raios-X: cada medição de RSSI entre um transmissor em
posição conhecida e um receptor em posição conhecida é uma **integral de linha** da atenuação
ao longo daquele raio. Se você acumular centenas de raios cruzando a casa em ângulos
diferentes, pode **resolver o problema inverso** e recuperar o mapa 2D de atenuação.

Paredes atenuam muito. Ar não atenua quase nada. Portanto: **o mapa de atenuação é,
aproximadamente, a planta baixa.**

- **Transmissores:** os APs Wi-Fi da sua casa e dos vizinhos — dezenas, de graça, 24/7.
- **Receptor móvel:** o celular (ou o laptop) andando pela casa.
- **Custo:** zero.
- **Resolução esperada:** ordem de 0,5 a 2 m. Detecta paredes; não detecta uma cadeira.
- **Calcanhar de aquiles:** você precisa saber **onde estava** em cada medição, e as posições
  dos APs são desconhecidas a princípio (é possível estimá-las junto — ver `docs/03`).

### 4.2 Mapeamento geométrico só com RSSI — *Structure from WiFi*

Há linha de pesquisa recente exatamente nisso. **"Structure from WiFi (SfW): RSSI-based
Geometric Mapping of Indoor Environments"** (ACC 2024) e o trabalho de **"inverse k-visibility"**
(*Autonomous Robots*, 2026) constroem um **mapa do espaço livre** de um ambiente desconhecido
usando **exclusivamente RSSI**. É pensado para robôs — a trajetória vem da odometria.

No seu caso, a "odometria do robô" vira: (a) você marcando manualmente onde está numa grade,
ou (b) dead reckoning da IMU do celular. A opção (a) é chata mas confiável; comece por ela.

### 4.3 BFI como fonte de informação **angular**

O achado mais elegante da pesquisa. Em 802.11ac/ax, o cliente devolve ao AP um *Compressed
Beamforming Report* com os ângulos que descrevem a matriz do canal. E:

> Os frames CBFR do 802.11ac/ax são transmitidos **antes** de a criptografia WPA2/WPA3 ser
> aplicada, então **qualquer dispositivo próximo em modo monitor consegue capturá-los**.

BFI é um **proxy de CSI que não exige firmware modificado** — a ferramenta de referência é a
**Wi-BFI**, open source, que reconstrói o BFI para SU/MU-MIMO em 20–160 MHz. Como os ângulos
descrevem direções espaciais, dá para extrair **AoA (ângulo de chegada)** aproximado dos
caminhos de multipercurso. Cada percurso forte é um **eco de uma parede**. Com AoA + posição,
você triangula refletores.

Isso é o mais próximo de "radar" que este hardware alcança. É também a parte mais difícil.

**Pré-requisito ambiental:** precisa haver tráfego 802.11ac com sounding na casa. Rede ociosa
em 2,4 GHz não gera nada.

### 4.4 Wi-Fi RTT (802.11mc) — se o roteador cooperar

O Android tem API nativa (`WifiRttManager`, API 28+) que mede **distância real por tempo de
voo**, com **1–2 m de precisão com 3+ APs**. Isso resolveria elegantemente o problema de
"onde eu estava". O app **WifiRttScan** do Google é gratuito e testa isso em minutos.

⚠️ Gargalo: depende do **AP** suportar FTM, e poucos roteadores domésticos suportam. Teste antes
de planejar em cima disso.

### 4.5 Bluetooth: pouca ajuda aqui

O BT do laptop é **4.2**. Isso significa **sem AoA/AoD** (introduzido no 5.1) e **sem Channel
Sounding** (BT 6.0, 2024 — método baseado em tempo/fase, bem mais preciso que RSSI). Sobra RSSI
de BLE, que serve como fonte extra de raios para a tomografia, não como fonte de geometria.

## 5. O que definitivamente **não** é possível aqui

| Ambição | Veredito | Por quê |
|---|---|---|
| Nuvem de pontos 3D do cômodo | ❌ | Exige fase coerente |
| Ver móveis, objetos, o que tem na mesa | ❌ | Objetos estáticos somem no background; resolução insuficiente |
| Pose humana estilo DensePose | ❌ | Exige CSI multi-antena + GPU + dataset rotulado |
| Reconstrução geométrica neural (GeRaF, 2026) | ❌ | Usa radar mmWave 77 GHz (~€2000) e 32 h de treino em H100 |
| Respiração através da parede | ❌ aqui | Demonstrado, mas sempre com CSI (ESP32-S3 + Pi, ~US$ 40) |
| **Mapa 2D de atenuação / planta baixa aproximada** | ✅ | **É o alvo deste projeto** |

## 6. Veredito

O projeto é viável **como tomografia RF de baixa resolução**, e isso já é um resultado
legítimo e pouco explorado por hobbistas. O que não é viável é a promessa das manchetes.

A boa notícia: o gargalo do projeto **não é o hardware**, é a **disciplina de medição** —
saber onde você estava, com que orientação, em cada amostra. Isso é resolvível com paciência
e fita crepe no chão, não com dinheiro.

E se um dia o custo zero for relaxado: **um ESP32-S3 de ~US$ 5–8 destrava CSI de verdade** e
muda o projeto de categoria. É o melhor upgrade por dólar que existe nesta área.
