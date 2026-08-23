# 11 — Glossário

---

## Camadas de sinal

**RSSI** *(Received Signal Strength Indicator)* — potência recebida, agregada sobre todas as
subportadoras e todos os caminhos de propagação. Um único número por pacote. Universalmente
disponível, sem root. É o que este projeto usa. Não contém fase.

**CSI** *(Channel State Information)* — amplitude **e fase** por subportadora OFDM, por par de
antenas. A medição rica que sustenta quase toda a literatura de Wi-Fi sensing. Exige NIC e
firmware específicos — **indisponível no QCA6174**.

**BFI** *(Beamforming Feedback Information)* — os ângulos comprimidos que um cliente devolve ao
AP para orientar o beamforming, transportados no **CBFR** *(Compressed Beamforming Report)*.
Funciona como proxy de CSI e, por especificação, **trafega em texto claro antes da criptografia
WPA2/WPA3** — logo é capturável em modo monitor por qualquer dispositivo próximo.

**Spectral scan** — recurso dos chipsets Atheros que despeja os **bins da FFT do baseband** via
debugfs. Mais rico que RSSI (energia por sub-banda), mas é magnitude: sem fase.

**IQ** *(In-phase / Quadrature)* — as amostras cruas do sinal, com fase preservada. Só via SDR.

## Grandezas

**dBm** — potência absoluta em decibéis relativos a 1 mW. RSSI típico de Wi-Fi: −30 dBm (colado
no AP) a −90 dBm (limiar de recepção).

**dB** — razão em decibéis. Usado aqui para atenuação: uma parede "de 6 dB" reduz a potência a
25% do que passaria sem ela.

**dB/m** — a unidade do mapa reconstruído: densidade de atenuação por metro percorrido.

**Expoente de perda de percurso (`n`)** — quão rápido o sinal decai com a distância no modelo
`P = A − 10·n·log₁₀(d)`. `n=2` no espaço livre; 3 a 4 típico em interiores.

**RMSE** *(Root Mean Square Error)* — erro do ajuste log-distance ao localizar um AP. Acima de
~6 dB, a posição estimada não é confiável.

## Técnicas de imageamento

**Tomografia por atenuação** — reconstruir um mapa 2D resolvendo o problema inverso sobre
integrais de linha de atenuação. **A técnica deste projeto.** Só precisa de potência.

**SAR** *(Synthetic Aperture Radar)* — mover um receptor para simular uma antena gigante,
combinando as medições **coerentemente**. Resolução de centímetros. **Exige fase.**

**Holografia de Wi-Fi** — tratar a frente de onda como holograma e reconstruir a cena 3D.
Demonstrada por Holl & Reinhard (PRL 2017) com uma antena fixa de referência e uma móvel.
**Exige gravação fase-coerente.**

**Problema inverso mal-posto** — aquele em que pequenas variações nos dados produzem grandes
variações na solução. Exige **regularização** para dar resultado estável.

**Regularização de Tikhonov** — adicionar `λ‖x‖²` ao objetivo, preferindo soluções de menor
energia onde não há evidência.

**Laplaciano discreto (`D`)** — operador que mede quanto uma célula difere das vizinhas.
Penalizá-lo (`μ‖Dx‖²`) favorece estruturas contínuas — como paredes.

**Gradiente projetado** — método de otimização que, a cada passo, projeta a solução de volta na
região viável. Aqui: `x ← max(x − lr·∇, 0)`, impondo densidade não-negativa.

## Rádio e propagação

**Multipercurso** *(multipath)* — o sinal chega por vários caminhos (direto + reflexões). Viola
a premissa de linha reta da tomografia e é a principal fonte de erro.

**Desvanecimento de pequena escala** *(small-scale fading)* — variação de vários dB ao mover o
receptor poucos centímetros, por interferência entre os percursos. Combatido com muitas amostras.

**Sounding** — troca em que o AP envia um frame de treinamento e o cliente responde com o CBFR.
**Sem sounding na rede, não há BFI para capturar.**

**Modo monitor** — modo em que a interface entrega todos os frames 802.11 do ar, sem associação.
Necessário para capturar BFI. Desconecta o Wi-Fi enquanto ativo.

**AoA / AoD** *(Angle of Arrival / Departure)* — direção de chegada ou saída do sinal. Exige
múltiplas antenas com fase relativa conhecida. Em Bluetooth, só a partir do **BT 5.1**.

**FTM / Wi-Fi RTT** *(Fine Time Measurement / Round-Trip Time)* — medição de distância por tempo
de voo, padronizada em **802.11mc** (e 802.11az). 1–2 m de precisão com 3+ APs. **Exige suporte
do AP**, o que poucos roteadores domésticos têm.

**Channel Sounding (Bluetooth)** — ranging por tempo/fase introduzido no **BT 6.0** (2024), bem
mais preciso que RSSI. Indisponível em BT 4.2.

**BSSID** — endereço MAC do rádio de um AP. Identifica um AP específico (um AP multibanda tem
BSSIDs distintos por banda). **É dado pessoal** — ver `docs/05`.

## Hardware e software citados

**`ath10k` / `ath9k`** — drivers Linux para chipsets Atheros. `ath9k` (802.11n) tem CSI tool;
`ath10k` (802.11ac, o desta máquina) **não tem**.

**PicoScenes** — plataforma de Wi-Fi sensing com CSI para Intel AX210/AX200, QCA9300, IWL5300 e SDRs.

**Nexmon** — modificação de firmware que extrai CSI de chips Broadcom/Cypress (Raspberry Pi,
alguns smartphones).

**ESP32 CSI Toolkit** — CSI em um microcontrolador de US$ 5–8. O caminho mais barato para CSI real.

**Wi-BFI** — ferramenta open source que extrai BFAs e reconstrói BFI de dispositivos comerciais.

**SDR** *(Software Defined Radio)* — rádio cujo processamento é feito em software, com acesso às
amostras IQ. HackRF, USRP. **Único caminho custo-não-zero que devolve fase.**

**802.11bf** — padrão IEEE de WLAN Sensing, em desenvolvimento desde 2020. Define negociação de
sessões de sensing e troca de medições em 2,4/5/6 GHz e 60 GHz.

## Métricas da literatura

**PCK@20** *(Percentage of Correct Keypoints)* — fração de articulações previstas dentro de 20%
de uma distância de referência. Usada em estimativa de pose. O RuView reporta ~2,5% com labels
proxy, contra meta de 35%+ — ou seja, essencialmente não funciona ainda.

**Ground truth** — a verdade medida independentemente, contra a qual se avalia o sistema.
Sem ela não há avaliação, apenas impressão. É a **fase 0** deste projeto.

**Fingerprinting** — localizar comparando a assinatura de sinal medida com um mapa previamente
coletado e rotulado. Alternativa à modelagem física; exige recoleta quando o ambiente muda.
