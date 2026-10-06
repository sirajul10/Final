from sqlalchemy import create_engine;
from sqlalchemy.orm import sessionmaker,declarative_base;


SQL_ALCHEMY_DADABASE_URL = "postgresql://postgres.wdhtntwsttuaasrrbdlp:Sujonhossain10@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

engine = create_engine(SQL_ALCHEMY_DADABASE_URL)

SessionLocal = sessionmaker(
    autocommit = False,
    autoflush=False,
    bind=engine

)

Base = declarative_base()