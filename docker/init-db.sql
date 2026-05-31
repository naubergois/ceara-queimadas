-- Inicialização do banco de dados PostgreSQL + PostGIS
-- Executado automaticamente na primeira inicialização do container

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Índices espaciais serão criados pelo Alembic/SQLAlchemy após a criação das tabelas
-- Este script apenas garante que as extensões estejam disponíveis

-- Tabela de áreas sensíveis (UCs, áreas urbanas, infraestrutura)
-- Populada via ETL separado com dados do IPECE/IBGE
CREATE TABLE IF NOT EXISTS areas_sensiveis (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(200) NOT NULL,
    tipo        VARCHAR(50) NOT NULL,  -- UC, AREA_URBANA, RODOVIA, HIDROGRAFIA, EQUIPAMENTO
    geom        GEOMETRY(GEOMETRY, 4326),
    populacao   INTEGER,
    criado_em   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_areas_sensiveis_geom ON areas_sensiveis USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_areas_sensiveis_tipo ON areas_sensiveis(tipo);

-- Tabela de histórico MapBiomas
CREATE TABLE IF NOT EXISTS historico_mapbiomas (
    id          SERIAL PRIMARY KEY,
    municipio   VARCHAR(100),
    ano         INTEGER,
    area_ha     FLOAT,
    tipo_veg    VARCHAR(100),
    geom        GEOMETRY(MULTIPOLYGON, 4326),
    criado_em   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mapbiomas_municipio ON historico_mapbiomas(municipio);
CREATE INDEX IF NOT EXISTS idx_mapbiomas_geom ON historico_mapbiomas USING GIST(geom);
