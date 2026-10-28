CREATE SCHEMA IF NOT EXISTS RECON;

DROP TABLE IF EXISTS RECON.LEDGER;
CREATE TABLE RECON.LEDGER (
    TXN_ID            DECIMAL(12,0),
    TXN_REF           VARCHAR(20),
    CUSTOMER_ID       DECIMAL(12,0),
    ACCOUNT_ID        DECIMAL(12,0),
    DEVICE_ID         DECIMAL(15,0),
    CITY              VARCHAR(30),
    MERCHANT_CATEGORY VARCHAR(30),
    CHANNEL           VARCHAR(10),
    AMOUNT            DECIMAL(14,2),
    CURRENCY          VARCHAR(3),
    TXN_TS            TIMESTAMP
);

DROP TABLE IF EXISTS RECON.BANK_STATEMENT;
CREATE TABLE RECON.BANK_STATEMENT (
    BANK_REF   VARCHAR(20),
    TXN_REF    VARCHAR(20),
    ACCOUNT_ID DECIMAL(12,0),
    AMOUNT     DECIMAL(14,2),
    VALUE_DATE DATE
);

DROP TABLE IF EXISTS RECON.FRAUD_TRUTH;
CREATE TABLE RECON.FRAUD_TRUTH (
    TXN_ID   DECIMAL(12,0),
    PATTERN  VARCHAR(30),
    IS_FRAUD DECIMAL(1,0)
);

DROP TABLE IF EXISTS RECON.CITY_DIM;
CREATE TABLE RECON.CITY_DIM (
    CITY    VARCHAR(30),
    COUNTRY VARCHAR(20)
);
INSERT INTO RECON.CITY_DIM VALUES
    ('Mumbai','India'), ('Delhi','India'), ('Bengaluru','India'),
    ('Hyderabad','India'), ('Chennai','India'), ('Kolkata','India'),
    ('Pune','India'), ('Ahmedabad','India'), ('Jaipur','India'),
    ('Lucknow','India'), ('Indore','India'), ('Kochi','India'),
    ('Lagos','Nigeria'), ('Dubai','UAE'), ('Singapore','Singapore'),
    ('Moscow','Russia'), ('Kyiv','Ukraine'), ('Bucharest','Romania');