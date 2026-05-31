# Fontes de Dados

## NASA FIRMS (implementado — dados reais)

- **O que é**: Fire Information for Resource Management System; focos VIIRS/MODIS
- **Como coletamos**: CSV público South America (24h e 7d), sem chave obrigatória
- **Serviço**: `firms_real.py` filtra bounding box do Ceará
- **Campos**: lat, lon, FRP (MW), temperatura do pixel, confiança, sensor, data_hora
- **Severidade**: calculada por FRP e confiança (baixa, media, alta, critica)
- **ID estável**: hash SHA256 de lat/lon/data/sensor para não quebrar ao atualizar cache

## Open-Meteo (implementado)

- Clima atual para municípios do Ceará e para coordenada de cada foco
- Temperatura, umidade, vento, precipitação, dias sem chuva
- Usado na explicação do agente e no painel climático

## Nominatim / OpenStreetMap (implementado)

- Geocodificação reversa: lat/lon → nome do município
- Rate limit ~1 req/s; geocodificação limitada a 40 focos na primeira resposta

## INPE BDQueimadas (planejado / modo completo)

- Focos oficiais Brasil; requer integração com banco

## GOES-16 (planejado / modo completo)

- Detecção quase em tempo real via NOAA S3
- FRP, persistência, evolução temporal

## FUNCEME e INMET (planejado)

- Clima regional Ceará; variáveis de seca e vento

## MapBiomas (planejado)

- Histórico de áreas queimadas e uso do solo
