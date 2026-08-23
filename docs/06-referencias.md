# 06 — Referências

<sub><b>intelie</b> · Classificação ISO 27001: <b>PÚBLICO</b> · Consultadas em 2026-08-23</sub>

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

## Padrão

- **IEEE 802.11bf (WLAN Sensing)** — em trabalho desde 2020; define negociação de sessões de
  sensing e troca de medições em 2,4/5/6 GHz e 60 GHz.
