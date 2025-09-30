import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# Função para buscar dados da NASA POWER API
def obter_irradiancia(lat, lon, start, end):
    """
    Consulta a API da NASA POWER e retorna irradiância (GHI) diária em kWh/m²/dia.
    start e end no formato YYYYMMDD (ex: 20240101).
    """
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point?"
        f"parameters=ALLSKY_SFC_SW_DWN&community=RE&longitude={lon}&latitude={lat}"
        f"&start={start}&end={end}&format=JSON"
    )
    
    r = requests.get(url)
    dados = r.json()
    irradiancia = dados['properties']['parameter']['ALLSKY_SFC_SW_DWN']
    
    df = pd.DataFrame.from_dict(irradiancia, orient='index', columns=['GHI'])
    df.index = pd.to_datetime(df.index)
    return df

# Função para calcular geração de energia
def calcular_geracao(ghi, pot_painel, ef_painel, qtd, ef_inversor):
    # GHI está em kWh/m²/dia → convertemos para energia gerada pelo sistema
    energia = ghi * (pot_painel/1000) * ef_painel * qtd * ef_inversor
    return energia

# Configuração da página
st.set_page_config(
    page_title="Challenge GoodWe", 
    page_icon="☀️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar para inputs do usuário
with st.sidebar:
    st.header("Configurações da Simulação")
    
    # Lista de cidades com lat/long aproximados e valores do kwh médios
    cidades = {
        "São Paulo": {"lat": -23.55, "lon": -46.63, "valor_kwh": 0.7},
        "Rio de Janeiro": {"lat": -22.91, "lon": -43.17, "valor_kwh": 0.87},
        "Brasília": {"lat": -15.78, "lon": -47.93, "valor_kwh": 0.96},
        "Salvador": {"lat": -12.97, "lon": -38.50, "valor_kwh": 0.82},
        "Fortaleza": {"lat": -3.73, "lon": -38.52, "valor_kwh": 0.72},
        "Belo Horizonte": {"lat": -19.92, "lon": -43.94, "valor_kwh": 0.65},
        "Manaus": {"lat": -3.12, "lon": -60.02, "valor_kwh": 0.83},
        "Curitiba": {"lat": -25.43, "lon": -49.27, "valor_kwh": 0.63},
        "Recife": {"lat": -8.05, "lon": -34.90, "valor_kwh": 0.706},
        "Porto Alegre": {"lat": -30.03, "lon": -51.23, "valor_kwh": 0.67}
    }
    
    cidade = st.selectbox("Cidade:", list(cidades.keys()))
    lat = cidades[cidade]["lat"]
    lon = cidades[cidade]["lon"]
    valor_medio_kwh = cidades[cidade]["valor_kwh"]
    
    st.divider()
    
    valor_kwh = st.number_input("Valor do kWh (R$):", min_value=0.0, value=valor_medio_kwh, step=0.01)
    consumo = st.number_input("Consumo mensal estimado (kWh):", min_value=0.0, value=300.0, step=10.0)
    
    st.divider()
    
    inversores = {
        "Inversor SDT G3.1": 0.985,
        "Microinversor MIS": 0.964,
        "Inversor XS G3": 0.976,
        "Inversores linha DNS G4": 0.981
    }
    inv = st.selectbox("Modelo do inversor:", list(inversores.keys()))
    ef_inv = inversores[inv]
    
    pot_painel = st.number_input("Potência do painel (W):", min_value=100, value=450, step=50)
    ef_painel = st.slider("Eficiência do painel:", min_value=0.1, max_value=0.3, value=0.18, step=0.01)
    qtd_paineis = st.slider("Quantidade de painéis:", min_value=1, max_value=50, value=6)
    
    st.divider()
    
    start_date = st.date_input("Data de início:", datetime(2024,1,1))
    end_date = st.date_input("Data final:", datetime(2024,12,31))
    
    st.divider()
    
    if st.button("Gerar Simulação", use_container_width=True):
        st.session_state.simulacao_gerada = True
        st.session_state.consumo = consumo  # Salva o consumo atual
        st.session_state.valor_kwh = valor_kwh  # Salva o valor do kWh atual
    else:
        if 'simulacao_gerada' not in st.session_state:
            st.session_state.simulacao_gerada = False

# Conteúdo principal
col1, col2, col3 = st.columns(3)
with col2:
    st.image("assets/logo.png", width=250)
st.caption("Analise a viabilidade e economia de um sistema de energia solar para sua residência ou empresa.")

if st.session_state.simulacao_gerada:
    # Converter datas para formato da API (YYYYMMDD)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    with st.spinner('Obtendo dados de irradiação solar...'):
        df = obter_irradiancia(lat, lon, start_str, end_str)

    # Calcular geração diária
    df['Geração Solar (kWh/dia)'] = calcular_geracao(df['GHI'], pot_painel, ef_painel, qtd_paineis, ef_inv)
    
    # Criar DataFrame mensal agrupando por mês
    df_mensal = df.resample('M').agg({
        'GHI': 'mean',
        'Geração Solar (kWh/dia)': 'sum'
    })
    df_mensal['Geração Solar (kWh/mês)'] = df_mensal['Geração Solar (kWh/dia)']
    df_mensal['Mês'] = df_mensal.index.strftime('%Y-%m')
    
    # Usar os valores atuais dos inputs (não os valores iniciais)
    consumo_atual = st.session_state.consumo
    valor_kwh_atual = st.session_state.valor_kwh
    
    # Custos mensais COM OS VALORES ATUAIS
    df_mensal['Custo sem Solar (R$)'] = consumo_atual * valor_kwh_atual
    df_mensal['Custo com Solar (R$)'] = ((consumo_atual - df_mensal['Geração Solar (kWh/mês)']).clip(lower=0)) * valor_kwh_atual
    df_mensal['Economia (R$)'] = df_mensal['Custo sem Solar (R$)'] - df_mensal['Custo com Solar (R$)']

    # Métricas de desempenho
    st.subheader("Desempenho do Sistema de Energia")
    
    economia_total = df_mensal['Economia (R$)'].sum()
    economia_media = df_mensal['Economia (R$)'].mean()
    autossuficiencia = (1 - (df_mensal['Custo com Solar (R$)'] / df_mensal['Custo sem Solar (R$)']).mean()) * 100
    geracao_total = df_mensal['Geração Solar (kWh/mês)'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Economia Total", f"R$ {economia_total:,.2f}", 
                 f"{economia_total/consumo_atual/len(df_mensal)*100:.1f}% do consumo")
    with col2:
        st.metric("Economia Mensal Média", f"R$ {economia_media:,.2f}")
    with col3:
        st.metric("Autossuficiência Média", f"{autossuficiencia:.1f}%")
    with col4:
        st.metric("Geração Total", f"{geracao_total:,.0f} kWh")

    # Gráficos
    tab1, tab2, tab3 = st.tabs(["Comparativo de Custos", "Geração de Energia", "Dados Detalhados"])
    
    with tab1:
        st.subheader("Comparativo de Custos Mensais")
        chart_data = df_mensal[['Custo sem Solar (R$)', 'Custo com Solar (R$)']]
        st.line_chart(
            chart_data,
            use_container_width=True,
            color=['#FF4B4B', '#00CC96']
        )
        
        # Gráfico de economia acumulada
        st.subheader("Economia Total")
        df_mensal['Economia Acumulada (R$)'] = df_mensal['Economia (R$)'].cumsum()
        st.area_chart(df_mensal[['Economia Acumulada (R$)']], color=['#00CC96'])
    
    with tab2:
        st.subheader("⚡ Geração de Energia Solar")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Gráfico de barras mensal
            st.bar_chart(
                df_mensal,
                x='Mês',
                y='Geração Solar (kWh/mês)',
                use_container_width=True,
                color='#0083B8'
            )
        
        with col2:
            # Métricas de geração
            st.metric("Geração Média Mensal", f"{df_mensal['Geração Solar (kWh/mês)'].mean():.1f} kWh")
            st.metric("Máxima Geração Mensal", f"{df_mensal['Geração Solar (kWh/mês)'].max():.1f} kWh")
            st.metric("Mínima Geração Mensal", f"{df_mensal['Geração Solar (kWh/mês)'].min():.1f} kWh")
            st.metric("Irradiação Média", f"{df_mensal['GHI'].mean():.2f} kWh/m²/dia")
    
    with tab3:
        st.subheader("Dados Detalhados Mensais")
        st.dataframe(
            df_mensal[['GHI', 'Geração Solar (kWh/mês)', 
                      'Custo sem Solar (R$)', 'Custo com Solar (R$)', 'Economia (R$)']].round(2),
            use_container_width=True
        )
        
        # Botão para download dos dados
        csv = df_mensal.to_csv(index=True).encode('utf-8')
        st.download_button(
            label="Download dos dados em CSV",
            data=csv,
            file_name="dados_simulacao_solar_mensal.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    # Tela inicial antes da simulação
    st.info("Configure os parâmetros do sistema na barra lateral e clique em 'Gerar Simulação' para começar.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sobre o Simulador")
        st.markdown("""
        Este simulador permite calcular:
        - Potencial de geração de energia solar
        - Economia na conta de energia elétrica
        - Payback do investimento
        - Desempenho ao longo do ano
        
        Os cálculos são baseados em dados reais de irradiação solar da NASA.
        """)
    
    with col2:
        st.subheader("Como Funciona")
        st.markdown("""
        1. Selecione sua localização
        2. Informe seu consumo médio de energia
        3. Configure o sistema solar desejado
        4. Clique em 'Gerar Simulação'
        
        O sistema utilizará dados históricos de irradiação solar para calcular 
        a geração de energia mensal estimada.
        """)
    
    st.divider()
    
    st.subheader("Mapa de Irradiação Solar no Brasil")
    # Mapa simplificado mostrando as cidades disponíveis
    map_data = pd.DataFrame({
        'lat': [-23.55, -22.91, -15.78, -12.97, -3.73, -19.92, -3.12, -25.43, -8.05, -30.03],
        'lon': [-46.63, -43.17, -47.93, -38.50, -38.52, -43.94, -60.02, -49.27, -34.90, -51.23],
        'cidade': list(cidades.keys())
    })
    
    st.map(map_data, zoom=3)
    st.caption("Cidades disponíveis para simulação no Brasil")