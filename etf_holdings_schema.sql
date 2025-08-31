-- ETF Holdings Database Schema
-- Extends existing stocks_listing table with comprehensive ETF composition data

-- 1. ETF Basic Information Table
CREATE TABLE etf_info (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    isin VARCHAR(32),                      -- International Securities ID
    expense_ratio DECIMAL(5,4),            -- Management Expense Ratio (MER)
    assets_under_management BIGINT,        -- Total AUM in dollars
    inception_date DATE,
    fund_family VARCHAR(100),              -- e.g., Vanguard, iShares, etc.
    category VARCHAR(100),                 -- e.g., Equity, Bond, Balanced
    investment_strategy TEXT,              -- Description of strategy
    benchmark_index VARCHAR(255),          -- What index it tracks
    currency VARCHAR(8) DEFAULT 'CAD',
    domicile VARCHAR(8) DEFAULT 'CA',      -- Country of domicile
    distribution_frequency VARCHAR(20),    -- Monthly, Quarterly, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Sector/Industry Classification Table
CREATE TABLE sectors (
    id BIGSERIAL PRIMARY KEY,
    sector_name VARCHAR(100) NOT NULL UNIQUE,    -- e.g., Technology, Healthcare
    sector_code VARCHAR(10),                     -- GICS sector code
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Geographic Regions Table
CREATE TABLE geographic_regions (
    id BIGSERIAL PRIMARY KEY,
    region_name VARCHAR(100) NOT NULL UNIQUE,   -- e.g., North America, Europe
    country_name VARCHAR(100),                  -- Specific country if applicable
    country_code VARCHAR(8),                    -- ISO country code
    region_type VARCHAR(20),                    -- Developed, Emerging, Frontier
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Enhanced Stock Information (extends existing stocks_listing conceptually)
CREATE TABLE stock_details (
    id BIGSERIAL PRIMARY KEY,
    listing_id BIGINT REFERENCES stocks_listing(id),  -- Link to existing table
    sector_id BIGINT REFERENCES sectors(id),
    region_id BIGINT REFERENCES geographic_regions(id),
    market_cap BIGINT,                         -- Market capitalization
    industry VARCHAR(150),                     -- More specific than sector
    headquarters_country VARCHAR(100),
    business_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. ETF Holdings (Main relationship table)
CREATE TABLE etf_holdings (
    id BIGSERIAL PRIMARY KEY,
    etf_id BIGINT REFERENCES etf_info(id),
    stock_listing_id BIGINT REFERENCES stocks_listing(id),
    weight_percentage DECIMAL(8,4) NOT NULL,   -- Percentage weight in ETF
    shares_held BIGINT,                        -- Number of shares held
    market_value BIGINT,                       -- Market value of holding
    as_of_date DATE NOT NULL,                  -- Holdings date (important!)
    data_source VARCHAR(50),                   -- Where data came from
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure no duplicate holdings for same ETF on same date
    UNIQUE(etf_id, stock_listing_id, as_of_date)
);

-- 6. ETF Sector Allocation (Aggregated view)
CREATE TABLE etf_sector_allocation (
    id BIGSERIAL PRIMARY KEY,
    etf_id BIGINT REFERENCES etf_info(id),
    sector_id BIGINT REFERENCES sectors(id),
    allocation_percentage DECIMAL(8,4) NOT NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(etf_id, sector_id, as_of_date)
);

-- 7. ETF Geographic Allocation
CREATE TABLE etf_geographic_allocation (
    id BIGSERIAL PRIMARY KEY,
    etf_id BIGINT REFERENCES etf_info(id),
    region_id BIGINT REFERENCES geographic_regions(id),
    allocation_percentage DECIMAL(8,4) NOT NULL,
    as_of_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(etf_id, region_id, as_of_date)
);

-- 8. Create indexes for performance
CREATE INDEX idx_etf_holdings_etf_id ON etf_holdings(etf_id);
CREATE INDEX idx_etf_holdings_stock_id ON etf_holdings(stock_listing_id);
CREATE INDEX idx_etf_holdings_date ON etf_holdings(as_of_date);
CREATE INDEX idx_etf_holdings_weight ON etf_holdings(weight_percentage DESC);

CREATE INDEX idx_stock_details_listing_id ON stock_details(listing_id);
CREATE INDEX idx_stock_details_sector ON stock_details(sector_id);
CREATE INDEX idx_stock_details_region ON stock_details(region_id);

-- 9. Insert some common sectors
INSERT INTO sectors (sector_name, sector_code, description) VALUES
('Technology', '45', 'Information Technology'),
('Healthcare', '35', 'Healthcare Equipment & Services, Pharmaceuticals'),
('Financials', '40', 'Banks, Insurance, Capital Markets'),
('Consumer Discretionary', '25', 'Automobiles, Retail, Media'),
('Communication Services', '50', 'Telecommunications, Media & Entertainment'),
('Industrials', '20', 'Aerospace, Defense, Transportation'),
('Consumer Staples', '30', 'Food, Beverage, Household Products'),
('Energy', '10', 'Oil, Gas, Renewable Energy'),
('Materials', '15', 'Chemicals, Construction Materials, Metals'),
('Real Estate', '60', 'REITs, Real Estate Management'),
('Utilities', '55', 'Electric, Gas, Water Utilities');

-- 10. Insert common geographic regions
INSERT INTO geographic_regions (region_name, country_name, country_code, region_type) VALUES
('North America', 'United States', 'US', 'Developed'),
('North America', 'Canada', 'CA', 'Developed'),
('Europe', 'United Kingdom', 'GB', 'Developed'),
('Europe', 'Germany', 'DE', 'Developed'),
('Europe', 'France', 'FR', 'Developed'),
('Asia Pacific', 'Japan', 'JP', 'Developed'),
('Asia Pacific', 'Australia', 'AU', 'Developed'),
('Emerging Markets', 'China', 'CN', 'Emerging'),
('Emerging Markets', 'India', 'IN', 'Emerging'),
('Emerging Markets', 'Brazil', 'BR', 'Emerging'),
('Emerging Markets', 'South Korea', 'KR', 'Emerging');

-- Useful queries for ETF analysis:

-- Get ETF holdings with stock details:
/*
SELECT 
    ei.symbol as etf_symbol,
    ei.name as etf_name,
    sl.symbol as stock_symbol,
    sl.name as stock_name,
    eh.weight_percentage,
    s.sector_name,
    gr.region_name,
    gr.country_name,
    eh.as_of_date
FROM etf_holdings eh
JOIN etf_info ei ON eh.etf_id = ei.id  
JOIN stocks_listing sl ON eh.stock_listing_id = sl.id
LEFT JOIN stock_details sd ON sd.listing_id = sl.id
LEFT JOIN sectors s ON sd.sector_id = s.id
LEFT JOIN geographic_regions gr ON sd.region_id = gr.id
WHERE ei.symbol = 'XGRO'
ORDER BY eh.weight_percentage DESC
LIMIT 20;
*/

-- Get ETF sector breakdown:
/*
SELECT 
    ei.symbol,
    s.sector_name,
    esa.allocation_percentage,
    esa.as_of_date
FROM etf_sector_allocation esa
JOIN etf_info ei ON esa.etf_id = ei.id
JOIN sectors s ON esa.sector_id = s.id  
WHERE ei.symbol = 'XGRO'
ORDER BY esa.allocation_percentage DESC;
*/
