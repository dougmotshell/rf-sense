# 06 — Referências

<sub>Consultadas em 2026-08-23</sub>

---

## Fundamento: imageamento coerente com Wi-Fi

- **Holl & Reinhard, "Holography of Wi-Fi Radiation"**, *Phys. Rev. Lett.* 118, 183901 (2017) —
  a referência canônica. Uma antena fixa + uma móvel, gravação fase-coerente, reconstrução 3D.
  <https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.118.183901> ·
  [arXiv](https://arxiv.org/pdf/1612.03194) ·
  [divulgação (APS Physics)](https://physics.aps.org/articles/v10/50)
- **"Resolving Full-Wave Through-Wall Transmission Effects in Multi-Static SAR"** — por que
  imagear através de parede quebra a hipótese de espalhamento único do SAR.
  <https://arxiv.org/html/2403.10354>

## O caminho deste projeto: mapeamento geométrico só com potência

- **"Structure from WiFi (SfW): RSSI-based Geometric Mapping of Indoor Environments"**,
  ACC 2024 — mapa do espaço livre usando exclusivamente RSSI.
  <https://arxiv.org/abs/2403.02235>
- **"Inverse k-visibility for RSSI-based Indoor geometric mapping"**, *Autonomous Robots* (2026)
  <https://link.springer.com/article/10.1007/s10514-026-10243-w>
- **P2SLAM: Bearing-based WiFi SLAM for Indoor Robots** (UC San Diego)
  <https://wcsng.ucsd.edu/p2slam/>
- **WiROS: WiFi sensing toolbox for robotics** <https://arxiv.org/pdf/2305.13418>

## Informação angular sem modificar firmware (BFI)

- **Wi-BFI: Extracting the IEEE 802.11 Beamforming Feedback Information from Commercial Wi-Fi
  Devices** — a ferramenta de referência. <https://arxiv.org/pdf/2309.04408> ·
  [código](https://github.com/kfoysalhaque/MU-MIMO-Beamforming-Feedback-Extraction-IEEE802.11ac)
- **"Bi-directional Beamforming Feedback-based Firmware-agnostic WiFi Sensing"**
  <https://arxiv.org/pdf/2112.06695>
- **BFId: Identity Inference Attacks Utilizing Beamforming Feedback Information**, CCS 2025 —
  o lado ofensivo do BFI. <https://dl.acm.org/doi/10.1145/3719027.3765062>

## Extração de CSI (para quando/se houver hardware)

- **PicoScenes** — AX210/AX200, QCA9300, IWL5300 e SDRs. <https://ps.zpj.io/>
- **Nexmon CSI** — Broadcom/Cypress, Raspberry Pi e alguns smartphones.
  <https://github.com/nexmonster/nexmon_csi>
- **ESP32 CSI Toolkit** — o caminho de US$ 5–8. <https://stevenmhernandez.github.io/ESP32-CSI-Tool/>
- **Atheros CSI Tool** — apenas `ath9k`. <https://github.com/xieyaxiongfly/Atheros_CSI_tool_OpenWRT_src>
- **"Free Your CSI: A CSI Extraction Platform for Modern Wi-Fi Chipsets"**
  <https://dl.acm.org/doi/10.1145/3349623.3355477>
- **"Tools and Methods for Achieving Wi-Fi Sensing in Embedded Devices"**, *Sensors* 25(19)
  <https://www.mdpi.com/1424-8220/25/19/6220>

## Spectral scan (Atheros)

- **Documentação do kernel — ath10k spectral scan**
  <https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath10k/spectral.html>
- **ath9k spectral scan** <https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath9k/spectral_scan.html>

## Ranging por tempo de voo

- **Wi-Fi RTT (802.11mc / 802.11az) — Android Developers**
  <https://developer.android.com/develop/connectivity/wifi/wifi-rtt>
- **AOSP — Wi-Fi RTT** <https://source.android.com/docs/core/connect/wifi-rtt>
- **WifiRttScan** (app gratuito do Google para testar suporte a FTM)
  <https://play.google.com/store/apps/details?id=com.google.android.apps.location.rtt.wifirttscan>
- **Notas críticas de B.K.P. Horn (MIT) sobre problemas práticos de FTM/RTT**
  <https://people.csail.mit.edu/bkph/ftmrtt_issues>

## Ground truth a custo zero (acústico)

- **BatMapper: Acoustic Sensing Based Indoor Floor Plan Construction Using Smartphones**,
  MobiCom — planta baixa com alto-falante e microfone do celular.
  <http://www.ece.stonybrook.edu/~fanye/papers/mobicom17-demo.pdf>
- **Smartphone-based Acoustic Indoor Space Mapping**, IMWUT
  <https://dl.acm.org/doi/10.1145/3214278>
- **Uncalibrated 3D Room Reconstruction from Sound** <https://arxiv.org/pdf/1606.06258>

## Reconstrução neural (estado da arte, fora de alcance)

- **NeRF²: Neural Radio-Frequency Radiance Fields**, MobiCom 2023
  <https://arxiv.org/pdf/2305.06118>
- **GeRaF: Neural Geometry Reconstruction from Radio Frequency Signals** (2026) — geometria 3D
  em resolução milimétrica, mas com radar mmWave 77 GHz e 32 h de treino em H100.
  <https://arxiv.org/html/2605.29097>
- **PropSplat: Map-Free RF Field Reconstruction via 3D Gaussian Propagation Splatting**
  <https://arxiv.org/pdf/2605.08035>

## Sensing de pessoas (as fontes divulgadas — ver `docs/04`)

- **RuView / WiFi-DensePose** <https://github.com/ruvnet/RuView> ·
  [avaliação equilibrada da CNX Software](https://www.cnx-software.com/2026/03/26/ruview-project-leverages-esp32-nodes-for-presence-detection-pose-estimation-and-breathing-heart-rate-monitoring/)
- **WhoFi (La Sapienza)** — reidentificação de pessoas por CSI, 95,5%
  <https://fastcompanybrasil.com/tech/pesquisadores-criam-sistema-wi-fi-que-ve-atraves-de-paredes/>
- **MIT Technology Review Brasil — "Como o Wi-Fi sensing se tornou uma tecnologia funcional"**
  <https://mittechreview.com.br/como-o-wi-fi-sensing-se-tornou-uma-tecnologia-funcional/>
- **"Human Presence Detection via Wi-Fi Range-Filtered Doppler Spectrum on Commodity Laptops"**
  (2026) — 94–96,5%, >6 m, mas com driver Intel modificado. <https://arxiv.org/html/2603.10845v2>
- **"Detection of presence and number of persons by a Wi-Fi signal: a practical RSSI-based
  approach"** <https://arxiv.org/pdf/2308.06773>
- **"Rethinking RSSI for WiFi sensing"**, *npj Wireless Technology*
  <https://www.nature.com/articles/s44459-026-00053-y>

## Padrão e ISAC

- **IEEE 802.11bf-2025 (WLAN Sensing)** — **ratificado em 26/09/2025**, emenda ao 802.11-2024.
  Define descoberta de capacidade, setup de sessão, troca e reporte de medições (amplitude,
  fase, atraso, Doppler, ângulo) em bandas isentas abaixo de 7,125 GHz e em 60 GHz direcional.
  Não define modelo de IA nem garante resultado. Ver [`14 §14.5`](14-as-cinco-camadas.md).
  <https://www.ieee802.org/11/Reports/tgbf_update.htm>
- **"IEEE 802.11bf WLAN Sensing Procedure: Enabling the Widespread Adoption of WiFi Sensing"** —
  o artigo de referência do procedimento. <https://ieeexplore.ieee.org/document/10467185/> ·
  [versão NIST](https://www.nist.gov/publications/ieee-80211bf-enabling-widespread-adoption-wi-fi-sensing)
- **"Toward Integrated Sensing and Communications in IEEE 802.11bf Wi-Fi Networks"**
  <https://arxiv.org/pdf/2212.13930>
- **"Integrated Sensing and Communication: Towards Multifunctional Perceptive Network"** (2025) —
  o mesmo movimento no lado celular (ISAC 5G/6G). <https://arxiv.org/pdf/2510.14358>
- ⚠️ Rótulo "Wi-Fi 6/6E/7" **não** implica suporte a 802.11bf — exige verificar chipset e
  firmware. Chegada estimada a roteador doméstico: 2027–2028.

## O campo ampliado (ver `docs/14` e `docs/15`)

- **Bilawal Sidhu, "AI Can See Without Cameras. WiFi Was Just the Beginning."** (31/07/2026) —
  o vídeo analisado em [`14`](14-as-cinco-camadas.md). Transcrição não obtida; a análise usa
  capítulos, descrição e as fontes citadas. <https://www.youtube.com/watch?v=olaQ3-m271M>
- **"Radio Frequency Sensing: How AI Sees Without Cameras"** — artigo-companheiro, 🔒 paywall
  além da prévia. <https://www.spatialintelligence.ai/p/radio-frequency-sensing-ai-without-cameras>
- **"Your WiFi Can See You. Here's How."** (17/03/2026) — o artigo anterior do mesmo autor;
  fonte da escada presença → pose → identidade.
  <https://www.spatialintelligence.ai/p/your-wifi-can-see-you-heres-how>
- **`gods-eye-view`** (MIT) — o projeto paralelo dele: 13 camadas de dados públicos num globo,
  código inspecionável, rastreamento individual recusado por design. Precedente de forma de
  entrega ([`15 §7`](15-viabilizar-na-pratica.md)). <https://github.com/bilawalsidhu/gods-eye-view>

### Camadas 3–5: fora de alcance aqui, citados para fechar a escada

- **MIT Vital-Radio** — sinais vitais por rádio, a referência do campo.
  <https://people.csail.mit.edu/hongzi/content/publications/Vital-Radio-Zhu.pdf>
- **Detecção de batimento através de parede com radar 24 GHz de canal único**
  <https://pmc.ncbi.nlm.nih.gov/>
- **"Millimeter-wave human detection and localization in complex indoor environments"**,
  *Remote Sensing* 16(14):2572 — <https://doi.org/10.3390/rs16142572>
- **RDGait** — identidade por marcha com radar de chip único. <https://doi.org/10.1145/3678552>
- **"Remote Monitoring of Human Vital Signs Based on 77-GHz mm-Wave FMCW Radar"**
  <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7285495/>
- **"A Survey of mmWave-based Human Sensing: Technology, Platform and Applications"**
  <https://arxiv.org/pdf/2308.03149>
- **Google Soli / Motion Sense** (60 GHz) e **Nest Hub Sleep Sensing** — o campo em produto de
  consumo. <https://blog.google/products-and-platforms/> ·
  <https://support.google.com/googlehome/>
- **Sense Through the Wall (US Army)** — a origem militar do campo.
  <https://www.army.mil/article/32868/>

### Espectro e regulação

- Pixel 4 não lançado na Índia por causa dos 60 GHz do Soli (WPC não havia liberado a faixa) —
  o caso concreto de regulação matando capacidade.
  <https://www.gsmarena.com/google_wont_sell_the_pixel_4_in_india_because_of_the_radar_hardware_inside-news-39643.php>
- **Ato Anatel nº 14448/2017** e alterações (nº 4776/2020, nº 423/2022, nº 14158/2025) — faixa
  57–71 GHz não licenciada e requisitos de 24,00–24,25 GHz narrowband.
  <https://informacoes.anatel.gov.br/legislacao/atos-de-certificacao-de-produtos/2017/1139-ato-14448>
