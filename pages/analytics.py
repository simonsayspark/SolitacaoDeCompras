import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

def load_page():
    """Análise avançada de dados Excel - Sistema Multi-Empresa de Gestão de Estoque"""
    
    # Header with company selector
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("📊 Análise de Estoque Multi-Empresa")
        st.markdown("**Ferramenta prática para gestão de estoque focada em AÇÃO e DECISÃO**")
    
    with col2:
        # Company selector
        empresa_selecionada = st.selectbox(
            "🏢 Empresa:",
            ["MINIPA", "MINIPA INDUSTRIA"],
            key="empresa_selector_analytics",
            help="Selecione a empresa para visualizar os dados de análise"
        )
        empresa_code = "MINIPA" if empresa_selecionada == "MINIPA" else "MINIPA_INDUSTRIA"
        
        # Store in session state for persistence
        st.session_state.current_empresa = empresa_code
    
    with col3:
        if st.button("🔄 Atualizar Dados", 
                    help="Atualizar dados do Snowflake (normalmente cache por 7 dias)",
                    use_container_width=True,
                    key="analytics_refresh"):
            from bd.snowflake_config import load_analytics_data
            load_analytics_data.clear()  # Clear specific function cache
            st.success("✅ Cache de análise limpo! Dados atualizados.")
            st.rerun()
    
    # Try to load data from Snowflake first
    try:
        from bd.snowflake_config import load_analytics_data, get_upload_versions
        
        # Get available versions for the selected company
        versions = get_upload_versions(empresa_code, "ANALYTICS", limit=20)
        
        # Version selector with custom names and filenames
        if versions:
            st.subheader(f"📦 Seleção de Versão - {empresa_selecionada}")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Create version options with custom names and filenames
                version_options = ["Versão Ativa (mais recente)"]
                version_mapping = {0: None}  # 0 = active version
                
                for i, v in enumerate(versions):
                    display_name = v.get('description', '').strip()
                    if not display_name:
                        display_name = f"Versão {v['version_id']}"
                    
                    filename_info = f" - 📁 {v.get('arquivo_origem', 'N/A')}" if v.get('arquivo_origem') else ""
                    option_text = f"{display_name} ({v['upload_date']}){filename_info}"
                    
                    version_options.append(option_text)
                    version_mapping[i + 1] = v['version_id']
                
                selected_option = st.selectbox(
                    "Escolha a versão dos dados:",
                    options=range(len(version_options)),
                    format_func=lambda x: version_options[x],
                    help="Selecione uma versão específica ou use a versão ativa"
                )
                
                selected_version_id = version_mapping[selected_option]
                
                if selected_version_id:
                    st.info(f"📊 Carregando versão específica: {version_options[selected_option]}")
                else:
                    st.info("📊 Carregando versão ativa (mais recente)")
            
            with col2:
                st.metric("📊 Versões Disponíveis", len(versions))
                active_versions = len([v for v in versions if v['is_active']])
                st.metric("🟢 Versão Ativa", f"{active_versions}/1")
        else:
            selected_version_id = None
            st.info(f"💡 Nenhuma versão de análise encontrada para {empresa_selecionada}")
        
        # Load data with company and version selection
        df = load_analytics_data(empresa=empresa_code, version_id=selected_version_id)
        
        if df is not None and len(df) > 0:
            version_text = f"v{selected_version_id}" if selected_version_id else "ativa"
            st.success(f"✅ {empresa_selecionada} - Análise {version_text}: {len(df)} produtos carregados")
            
            # Check if data_upload column exists before accessing it
            if 'data_upload' in df.columns:
                st.info(f"📅 Data do upload: {df['data_upload'].max()}")
            else:
                st.info("📅 Dados de análise carregados da nuvem")
                
        else:
            st.info(f"💡 Nenhum dado de análise encontrado para {empresa_selecionada}.")
            st.markdown("👉 **Vá para 'Upload de Dados' e selecione '📊 Análise de Estoque (Export)' para enviar dados para esta empresa primeiro.**")
            df = None
            
    except ImportError:
        st.warning("⚠️ Snowflake não configurado. Usando upload local temporário.")
        df = None
        empresa_code = "MINIPA"  # Default for fallback
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados de análise para {empresa_selecionada}: {str(e)}")
        df = None

    # Fallback to local upload if no cloud data
    if df is None:
        st.subheader("📁 Upload Local (Temporário)")
        st.markdown("⚠️ **Este upload é temporário. Para salvar na nuvem, use 'Upload de Dados' → 'Análise de Estoque'**")
        
        uploaded_file = st.file_uploader(
            "Faça upload do arquivo Excel (.xlsx)",
            type=['xlsx'],
            help="Arquivo deve conter planilha 'Export' com colunas: Produto, Estoque, Média 6 Meses, Estoque Cobertura, MOQ, UltimoFor"
        )
        
        if uploaded_file is not None:
            try:
                # Read the Excel file
                df = pd.read_excel(uploaded_file, sheet_name='Export')
                
                # Clean data
                df = df.dropna(subset=['Produto'])
                df = df[df['Produto'] != 'nan']
                df = df[~df['Produto'].str.contains('Filtros aplicados', na=False)]
                
                # Convert numeric columns
                numeric_columns = ['Estoque', 'Média 6 Meses', 'Estoque Cobertura', 'Qtde Tot Compras', 'MOQ']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # Handle supplier column - fill empty values with Brazil
                if 'UltimoFornecedor' in df.columns:
                    df['UltimoFornecedor'] = df['UltimoFornecedor'].fillna('Brazil')
                    df.loc[df['UltimoFornecedor'].str.strip() == '', 'UltimoFornecedor'] = 'Brazil'
                
                st.success(f"✅ Dados carregados: {len(df)} produtos")
                
            except Exception as e:
                st.error(f"❌ Erro ao processar arquivo: {str(e)}")
                st.info("💡 Certifique-se de que o arquivo contém uma planilha 'Export' com as colunas necessárias")
                return
        else:
            st.info("📁 Faça upload de um arquivo Excel para análise local ou use os dados da nuvem")
            
            # Show sample format
            with st.expander("📋 Formato esperado do arquivo"):
                st.markdown("""
                **Planilha: 'Export'**
                
                Colunas necessárias:
                - `Produto`: Nome do produto
                - `Estoque`: Quantidade atual em estoque
                - `Média 6 Meses`: Consumo médio mensal
                - `Estoque Cobertura`: Cobertura em meses
                - `MOQ`: Quantidade mínima de pedido
                - `UltimoFor`: Último fornecedor (deixe vazio para 'Brazil')
                - `Qtde Tot Compras`: Quantidade total para compras (opcional)
                """)
            return

    # Only show analysis if data is loaded (either from Snowflake or local upload)
    if df is not None:
        # Handle different column name formats (timeline vs analytics)
        df_processed = df.copy()
        
        # Map timeline columns to analytics columns if needed
        column_mapping = {
            'Item': 'Produto',
            'Modelo': 'Produto', 
            'Estoque_Total': 'Estoque',
            'Vendas_Medias': 'Média 6 Meses',
            'UltimoFor': 'UltimoFornecedor'  # NEW MAPPING
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df_processed[new_col] = df[old_col]
        
        # Calculate Estoque Cobertura if missing
        if 'Estoque Cobertura' not in df_processed.columns:
            if 'Estoque' in df_processed.columns and 'Média 6 Meses' in df_processed.columns:
                df_processed['Estoque Cobertura'] = df_processed.apply(
                    lambda row: row['Estoque'] / row['Média 6 Meses'] if row['Média 6 Meses'] > 0 else 999, 
                    axis=1
                )
        
        # Use processed dataframe
        df = df_processed
        
        # Separate new and existing products
        produtos_novos = df[(df.get('Estoque', 0) == 0) & (df.get('Média 6 Meses', 0) == 0) & (df.get('Qtde Tot Compras', 0) > 0)]
        produtos_existentes = df[(df.get('Estoque', 0) > 0) | (df.get('Média 6 Meses', 0) > 0)]
        
        # Show company context
        st.info(f"📊 **Análise para {empresa_selecionada}** | Versão: {f'v{selected_version_id}' if 'selected_version_id' in locals() and selected_version_id else 'Ativa'}")
        
        # Show analytics tabs with company context
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            f"📋 Resumo - {empresa_selecionada}", 
            f"🚨 Lista de Compras - {empresa_selecionada}", 
            f"📊 Dashboards - {empresa_selecionada}", 
            f"📞 Contatos Urgentes - {empresa_selecionada}",
            f"📋 Tabela Geral - {empresa_selecionada}"
        ])
        
        with tab1:
            show_executive_summary(df, produtos_novos, produtos_existentes, empresa_selecionada)
        
        with tab2:
            show_purchase_list(produtos_existentes, empresa_selecionada)
        
        with tab3:
            show_analytics_dashboard(produtos_existentes, produtos_novos, empresa_selecionada)
        
        with tab4:
            show_urgent_contacts(produtos_existentes, empresa_selecionada)
        
        with tab5:
            show_tabela_geral(df, empresa_selecionada)

def show_executive_summary(df, produtos_novos, produtos_existentes, empresa="MINIPA"):
    """Resumo executivo dos dados por empresa"""
    
    st.subheader(f"📋 Resumo Executivo - {empresa}")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📦 Total de Produtos", len(df))
    
    with col2:
        st.metric("🆕 Produtos Novos", len(produtos_novos))
    
    with col3:
        st.metric("📈 Produtos Existentes", len(produtos_existentes))
    
    with col4:
        if len(produtos_existentes) > 0:
            criticos = len(produtos_existentes[produtos_existentes['Estoque Cobertura'] <= 1])
            st.metric("🚨 Produtos Críticos", criticos)
        else:
            st.metric("🚨 Produtos Críticos", 0)
    
    if len(produtos_existentes) > 0:
        # Status breakdown
        st.subheader("🎯 Status dos Produtos Existentes")
        
        criticos = len(produtos_existentes[produtos_existentes['Estoque Cobertura'] <= 1])
        alerta = len(produtos_existentes[(produtos_existentes['Estoque Cobertura'] > 1) & (produtos_existentes['Estoque Cobertura'] <= 3)])
        saudaveis = len(produtos_existentes[produtos_existentes['Estoque Cobertura'] > 3])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "🔴 Críticos (≤1 mês)", 
                criticos,
                delta=f"{criticos/len(produtos_existentes)*100:.1f}%"
            )
        
        with col2:
            st.metric(
                "🟡 Alerta (1-3 meses)", 
                alerta,
                delta=f"{alerta/len(produtos_existentes)*100:.1f}%"
            )
        
        with col3:
            st.metric(
                "🟢 Saudáveis (>3 meses)", 
                saudaveis,
                delta=f"{saudaveis/len(produtos_existentes)*100:.1f}%"
            )
        
        # Financial overview
        st.subheader("💰 Visão Financeira")
        
        estoque_total = produtos_existentes['Estoque'].sum()
        consumo_total = produtos_existentes['Média 6 Meses'].sum()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📦 Estoque Total", f"{estoque_total:,.0f} unidades")
        
        with col2:
            st.metric("📈 Consumo Mensal", f"{consumo_total:,.1f} unidades")
        
        with col3:
            if consumo_total > 0:
                duracao = estoque_total / consumo_total
                st.metric("⏱️ Duração Média", f"{duracao:.1f} meses")
            else:
                st.metric("⏱️ Duração Média", "N/A")
    
    # Action items
    if len(produtos_existentes) > 0:
        st.subheader("🚨 Ações Necessárias")
        
        if criticos > 0:
            st.error(f"⚡ URGENTE: {criticos} produtos críticos precisam de compra IMEDIATA")
        if alerta > 0:
            st.warning(f"📅 PLANEJAR: {alerta} produtos em alerta para próximas semanas")
        if len(produtos_novos) > 0:
            st.info(f"🆕 MONITORAR: {len(produtos_novos)} produtos novos sendo lançados")
        
        if criticos == 0 and alerta == 0:
            st.success("✅ Situação de estoque sob controle!")

def calculate_purchase_suggestions(produtos_existentes):
    """Calculate purchase suggestions for products"""
    
    def calcular_quando_vai_acabar(estoque, consumo_mensal):
        if consumo_mensal <= 0:
            return "Sem consumo", 999
        
        meses_restantes = estoque / consumo_mensal
        
        if meses_restantes <= 0:
            return "JÁ ACABOU", 0
        elif meses_restantes < 0.5:
            dias = int(meses_restantes * 30)
            return f"{dias} dias", meses_restantes
        else:
            return f"{meses_restantes:.1f} meses", meses_restantes
    
    def quanto_comprar(consumo_mensal, estoque_atual, moq=0, meses_desejados=6):
        if consumo_mensal <= 0:
            return moq if moq > 0 else 0
        
        estoque_ideal = consumo_mensal * meses_desejados
        falta = max(0, estoque_ideal - estoque_atual)
        
        if falta <= 0:
            return 0
        
        # Use MOQ if available, otherwise round to 50s
        if moq > 0:
            # Calculate multiples of MOQ needed
            multiplos = max(1, int(np.ceil(falta / moq)))
            return multiplos * moq
        else:
            # Round for easier purchasing
            return int(np.ceil(falta / 50) * 50)
    
    # Calculate for each product
    suggestions = []
    
    for _, row in produtos_existentes.iterrows():
        produto = str(row['Produto'])
        estoque = row['Estoque']
        consumo = row['Média 6 Meses']
        moq = row.get('MOQ', 0) if 'MOQ' in row.index else 0
        fornecedor = row.get('UltimoFornecedor', 'Brazil') if 'UltimoFornecedor' in row.index else 'Brazil'
        
        quando_acaba, meses_num = calcular_quando_vai_acabar(estoque, consumo)
        qtd_comprar = quanto_comprar(consumo, estoque, moq)
        
        suggestions.append({
            'Produto': produto,
            'Estoque_Atual': estoque,
            'Consumo_Mensal': consumo,
            'MOQ': moq,
            'Fornecedor': fornecedor,
            'Quando_Acaba': quando_acaba,
            'Meses_Restantes': meses_num,
            'Qtd_Comprar': qtd_comprar,
            'Investimento_Estimado': qtd_comprar * 15  # R$ 15 per unit estimate
        })
    
    return pd.DataFrame(suggestions)

def show_purchase_list(produtos_existentes, empresa="MINIPA"):
    """Show practical purchase list by company"""
    
    st.subheader(f"🛒 Lista Prática de Compras - {empresa}")
    
    if len(produtos_existentes) == 0:
        st.info("Nenhum produto existente para análise")
        return
    
    # Calculate suggestions
    suggestions_df = calculate_purchase_suggestions(produtos_existentes)
    
    # Filter products that need action (increased range due to new categories)
    precisa_acao = suggestions_df[
        (suggestions_df['Meses_Restantes'] <= 6) & 
        (suggestions_df['Consumo_Mensal'] > 0)
    ].sort_values('Meses_Restantes')
    
    if len(precisa_acao) == 0:
        st.success("✅ Nenhum produto necessita compra urgente!")
        return
    
    st.info(f"📦 {len(precisa_acao)} produtos precisam de compra")
    
    # Emergency products (≤ 1 month)
    emergencia = precisa_acao[precisa_acao['Meses_Restantes'] <= 1]
    if len(emergencia) > 0:
        st.error("🚨 EMERGÊNCIA (≤ 1 mês)")
        st.dataframe(
            emergencia[['Produto', 'Fornecedor', 'Quando_Acaba', 'MOQ', 'Qtd_Comprar', 'Investimento_Estimado']].round(1),
            use_container_width=True
        )
    
    # Critical products (1-3 months)
    criticos = precisa_acao[(precisa_acao['Meses_Restantes'] > 1) & (precisa_acao['Meses_Restantes'] <= 3)]
    if len(criticos) > 0:
        st.warning("🔴 CRÍTICOS (1-3 meses)")
        st.dataframe(
            criticos[['Produto', 'Fornecedor', 'Quando_Acaba', 'MOQ', 'Qtd_Comprar', 'Investimento_Estimado']].head(10).round(1),
            use_container_width=True
        )
    
    # Attention products (3+ months)
    atencao = precisa_acao[precisa_acao['Meses_Restantes'] > 3]
    if len(atencao) > 0:
        st.info("🟡 ATENÇÃO (>3 meses)")
        st.dataframe(
            atencao[['Produto', 'Fornecedor', 'Quando_Acaba', 'MOQ', 'Qtd_Comprar', 'Investimento_Estimado']].head(10).round(1),
            use_container_width=True
        )
    
    # Summary
    st.subheader("💰 Resumo de Investimento")
    
    total_emergencia = len(emergencia)
    total_criticos = len(criticos)
    total_atencao = len(atencao)
    
    investimento_total = precisa_acao['Investimento_Estimado'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🚨 Emergência", total_emergencia)
    with col2:
        st.metric("🔴 Críticos", total_criticos)
    with col3:
        st.metric("🟡 Atenção", total_atencao)
    with col4:
        st.metric("💰 Investimento", f"R$ {investimento_total:,.0f}")

def show_analytics_dashboard(produtos_existentes, produtos_novos, empresa="MINIPA"):
    """Show visual analytics dashboard by company"""
    
    st.subheader(f"📊 Dashboard Visual - {empresa}")
    
    if len(produtos_existentes) == 0:
        st.info("Nenhum produto para análise visual")
        return
    
    # Calculate data for charts
    suggestions_df = calculate_purchase_suggestions(produtos_existentes)
    
    # Urgency categorization
    muito_critico = len(suggestions_df[suggestions_df['Meses_Restantes'] <= 1])
    critico = len(suggestions_df[(suggestions_df['Meses_Restantes'] > 1) & (suggestions_df['Meses_Restantes'] <= 3)])
    moderado = len(suggestions_df[(suggestions_df['Meses_Restantes'] > 3) & (suggestions_df['Meses_Restantes'] <= 6)])
    ok = len(suggestions_df[suggestions_df['Meses_Restantes'] > 6])
    
    # Chart 1: Products by urgency
    col1, col2 = st.columns(2)
    
    with col1:
        urgency_data = {
            'Categoria': ['≤1 mês', '1-3 meses', '3-6 meses', '>6 meses'],
            'Quantidade': [muito_critico, critico, moderado, ok],
            'Cor': ['#8B0000', '#FF0000', '#FFA500', '#008000']
        }
        
        fig_urgency = px.bar(
            urgency_data,
            x='Categoria',
            y='Quantidade',
            color='Cor',
            title='🚨 Produtos por Urgência',
            color_discrete_map={color: color for color in urgency_data['Cor']}
        )
        st.plotly_chart(fig_urgency, use_container_width=True)
    
    with col2:
        # Chart 2: Stock coverage distribution
        if len(produtos_existentes) > 0:
            fig_pie = px.pie(
                values=[muito_critico, critico, moderado, ok],
                names=['≤1 mês', '1-3 meses', '3-6 meses', '>6 meses'],
                title='⏰ Distribuição de Cobertura',
                color_discrete_sequence=['#8B0000', '#FF0000', '#FFA500', '#008000']
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    
    # Chart 3: Top products to buy
    precisa_acao = suggestions_df[
        (suggestions_df['Meses_Restantes'] <= 3) & 
        (suggestions_df['Consumo_Mensal'] > 0)
    ].sort_values('Qtd_Comprar', ascending=False).head(10)
    
    if len(precisa_acao) > 0:
        fig_top = px.bar(
            precisa_acao,
            x='Qtd_Comprar',
            y='Produto',
            orientation='h',
            title='🛒 Top 10 Produtos para Comprar',
            color='Meses_Restantes',
            color_continuous_scale='Reds_r'
        )
        fig_top.update_layout(height=500)
        st.plotly_chart(fig_top, use_container_width=True)
    
    # Chart 4: Supplier analysis
    if 'Fornecedor' in suggestions_df.columns:
        st.subheader("🏭 Análise por Fornecedor")
        
        # Group by supplier
        supplier_analysis = suggestions_df.groupby('Fornecedor').agg({
            'Produto': 'count',
            'Qtd_Comprar': 'sum',
            'Investimento_Estimado': 'sum',
            'Meses_Restantes': 'mean'
        }).round(1)
        supplier_analysis.columns = ['Produtos', 'Qtd_Total', 'Investimento', 'Urgência_Média']
        supplier_analysis = supplier_analysis.sort_values('Investimento', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top suppliers by investment
            fig_suppliers = px.bar(
                supplier_analysis.head(10).reset_index(),
                x='Investimento',
                y='Fornecedor',
                orientation='h',
                title='💰 Top Fornecedores por Investimento',
                color='Urgência_Média',
                color_continuous_scale='Reds_r'
            )
            st.plotly_chart(fig_suppliers, use_container_width=True)
        
        with col2:
            # Supplier distribution
            fig_supplier_pie = px.pie(
                supplier_analysis.reset_index(),
                values='Produtos',
                names='Fornecedor',
                title='📊 Distribuição de Produtos por Fornecedor'
            )
            st.plotly_chart(fig_supplier_pie, use_container_width=True)
        
        # Show supplier summary table
        st.dataframe(supplier_analysis, use_container_width=True)
    
    # Chart 5: Investment timeline
    col1, col2 = st.columns(2)
    
    with col1:
        emergencia = suggestions_df[suggestions_df['Meses_Restantes'] <= 1]
        criticos_chart = suggestions_df[(suggestions_df['Meses_Restantes'] > 1) & (suggestions_df['Meses_Restantes'] <= 3)]
        atencao = suggestions_df[suggestions_df['Meses_Restantes'] > 3]
        
        invest_emergencia = emergencia['Investimento_Estimado'].sum() if len(emergencia) > 0 else 0
        invest_criticos = criticos_chart['Investimento_Estimado'].sum() if len(criticos_chart) > 0 else 0
        invest_atencao = atencao['Investimento_Estimado'].sum() if len(atencao) > 0 else 0
        
        investment_data = {
            'Período': ['Este Mês', 'Próximos 3 Meses', 'Longo Prazo'],
            'Investimento': [invest_emergencia, invest_criticos, invest_atencao]
        }
        
        fig_invest = px.bar(
            investment_data,
            x='Período',
            y='Investimento',
            title='💰 Investimento por Período',
            color='Investimento',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig_invest, use_container_width=True)
    
    with col2:
        # Product status overview
        if len(produtos_novos) > 0:
            overview_data = {
                'Categoria': ['Produtos Existentes', 'Produtos Novos'],
                'Quantidade': [len(produtos_existentes), len(produtos_novos)]
            }
            
            fig_overview = px.pie(
                overview_data,
                values='Quantidade',
                names='Categoria',
                title='📊 Visão Geral dos Produtos'
            )
            st.plotly_chart(fig_overview, use_container_width=True)

def show_urgent_contacts(produtos_existentes, empresa="MINIPA"):
    """Show urgent contacts list by company"""
    
    st.subheader(f"📞 Contatos Urgentes - {empresa}")
    
    if len(produtos_existentes) == 0:
        st.info("Nenhum produto para análise de contatos")
        return
    
    # Get critical products
    criticos = produtos_existentes[produtos_existentes['Estoque Cobertura'] <= 1]
    
    if len(criticos) == 0:
        st.success("✅ Nenhum produto crítico no momento!")
        return
    
    st.error(f"🚨 {len(criticos)} produtos críticos precisam de ação IMEDIATA!")
    
    # Show critical products list
    st.subheader("🔴 Lista de Produtos Críticos")
    
    # Sample contact info (in real app, this would come from database)
    contact_data = []
    for _, row in criticos.head(10).iterrows():
        contact_data.append({
            'Produto': row['Produto'],
            'Estoque': f"{row['Estoque']:.0f}",
            'Cobertura': f"{row['Estoque Cobertura']:.1f} meses",
            'Status': "🚨 CRÍTICO",
            'Ação': "Comprar AGORA"
        })
    
    if contact_data:
        contact_df = pd.DataFrame(contact_data)
        st.dataframe(contact_df, use_container_width=True)
    
    # Contact instructions
    st.subheader("📋 Instruções de Contato")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **🏢 Departamento de Compras:**
        - Email: compras@empresa.com
        - Tel: (11) 1234-5678
        - WhatsApp: (11) 98765-4321
        """)
    
    with col2:
        st.markdown("""
        **⏰ Horário de Atendimento:**
        - Segunda a Sexta: 8h às 18h
        - Urgências: 24h via WhatsApp
        - Email: Resposta em até 2h
        """)
    
    # Quick actions
    st.subheader("⚡ Ações Rápidas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📧 Abrir Email", use_container_width=True):
            st.info("Email aberto com lista de produtos críticos")
    
    with col2:
        if st.button("📱 WhatsApp", use_container_width=True):
            st.info("WhatsApp aberto para contato urgente")
    
    with col3:
        if st.button("📊 Exportar Lista", use_container_width=True):
            st.info("Lista de produtos críticos exportada")

def show_tabela_geral(df, empresa="MINIPA"):
    """Show complete data table with search, filter and export functionality"""
    
    st.subheader(f"📋 Tabela Geral - {empresa}")
    
    if df is None or len(df) == 0:
        st.info("Nenhum dado disponível para exibir")
        return
    
    # Remove metadata columns from display - FORCE REMOVAL
    metadata_columns = ['data_upload', 'upload_version', 'version_id', 'upload_date', 'created_by', 'is_active']
    clean_df = df.copy()
    
    # Remove metadata columns if they exist - more comprehensive
    for col in metadata_columns:
        if col in clean_df.columns:
            clean_df = clean_df.drop(columns=[col])
    
    # Also remove any columns that start with these patterns
    columns_to_remove = []
    for col in clean_df.columns:
        if any(pattern in col.lower() for pattern in ['upload', 'version', 'created', 'active']):
            columns_to_remove.append(col)
    
    for col in columns_to_remove:
        clean_df = clean_df.drop(columns=[col])
    
    # Search and filter controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input("🔍 Buscar produto:", placeholder="Digite o nome do produto...")
    
    with col2:
        # Filter by stock coverage if available
        if 'Estoque Cobertura' in clean_df.columns:
            coverage_filter = st.selectbox(
                "📊 Filtrar por cobertura:",
                ["Todos", "Críticos (≤1 mês)", "Alerta (1-3 meses)", "Saudáveis (>3 meses)"]
            )
        else:
            coverage_filter = "Todos"
    
    with col3:
        # Export button
        if st.button("📥 Exportar Excel", use_container_width=True):
            # Create Excel export
            try:
                import io
                from datetime import datetime
                
                # Prepare clean data for export (no metadata columns)
                export_df = clean_df.copy()
                
                # Create a BytesIO buffer
                buffer = io.BytesIO()
                
                # Write to Excel using openpyxl (built into pandas)
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    export_df.to_excel(writer, sheet_name=f'{empresa}_Dados_Completos', index=False)
                
                # Get the data
                buffer.seek(0)
                
                # Download button
                st.download_button(
                    label="⬇️ Download Excel",
                    data=buffer.getvalue(),
                    file_name=f"{empresa}_dados_completos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success("✅ Arquivo Excel preparado para download!")
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar Excel: {str(e)}")
                st.info("💡 Tentando método alternativo...")
                
                # Fallback method using CSV
                try:
                    csv_data = export_df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download CSV (alternativo)",
                        data=csv_data,
                        file_name=f"{empresa}_dados_completos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                    st.success("✅ Arquivo CSV preparado para download!")
                except Exception as e2:
                    st.error(f"❌ Erro no método alternativo: {str(e2)}")
    
    # Apply filters
    filtered_df = clean_df.copy()
    
    # Search filter
    if search_term:
        if 'Produto' in filtered_df.columns:
            mask = filtered_df['Produto'].astype(str).str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[mask]
    
    # Coverage filter
    if coverage_filter != "Todos" and 'Estoque Cobertura' in filtered_df.columns:
        if coverage_filter == "Críticos (≤1 mês)":
            filtered_df = filtered_df[filtered_df['Estoque Cobertura'] <= 1]
        elif coverage_filter == "Alerta (1-3 meses)":
            filtered_df = filtered_df[(filtered_df['Estoque Cobertura'] > 1) & (filtered_df['Estoque Cobertura'] <= 3)]
        elif coverage_filter == "Saudáveis (>3 meses)":
            filtered_df = filtered_df[filtered_df['Estoque Cobertura'] > 3]
    
    # Show results count
    st.info(f"📊 Exibindo {len(filtered_df)} de {len(clean_df)} produtos")
    
    # Display the table
    if len(filtered_df) > 0:
        # Format numeric columns for better display
        display_df = filtered_df.copy()
        
        # Round numeric columns
        numeric_columns = display_df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if col in ['Estoque', 'Consumo 6 Meses', 'Média 6 Meses']:
                display_df[col] = display_df[col].round(0).astype(int)
            elif col in ['Estoque Cobertura']:
                display_df[col] = display_df[col].round(2)
            else:
                display_df[col] = display_df[col].round(1)
        
        # Create dynamic column config based on available columns
        column_config = {}
        if "Produto" in display_df.columns:
            column_config["Produto"] = st.column_config.TextColumn("Produto", width="medium")
        if "Estoque" in display_df.columns:
            column_config["Estoque"] = st.column_config.NumberColumn("Estoque", format="%d")
        if "Consumo 6 Meses" in display_df.columns:
            column_config["Consumo 6 Meses"] = st.column_config.NumberColumn("Consumo 6M", format="%d")
        if "Média 6 Meses" in display_df.columns:
            column_config["Média 6 Meses"] = st.column_config.NumberColumn("Média 6M", format="%d")
        if "Estoque Cobertura" in display_df.columns:
            column_config["Estoque Cobertura"] = st.column_config.NumberColumn("Cobertura", format="%.2f meses")
        if "MOQ" in display_df.columns:
            column_config["MOQ"] = st.column_config.NumberColumn("MOQ", format="%d")
        if "UltimoFornecedor" in display_df.columns:
            column_config["UltimoFornecedor"] = st.column_config.TextColumn("Último Fornecedor", width="medium")
        
        # Show the dataframe with pagination
        st.dataframe(
            display_df,
            use_container_width=True,
            height=600,
            column_config=column_config
        )
        
        # Summary statistics
        st.subheader("📈 Estatísticas Resumidas")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'Estoque' in filtered_df.columns:
                total_estoque = filtered_df['Estoque'].sum()
                st.metric("📦 Estoque Total", f"{total_estoque:,.0f}")
        
        with col2:
            if 'Média 6 Meses' in filtered_df.columns:
                media_consumo = filtered_df['Média 6 Meses'].mean()
                st.metric("📊 Consumo Médio", f"{media_consumo:.1f}")
        
        with col3:
            if 'Estoque Cobertura' in filtered_df.columns:
                cobertura_media = filtered_df['Estoque Cobertura'].mean()
                st.metric("⏱️ Cobertura Média", f"{cobertura_media:.1f} meses")
        
        with col4:
            if 'MOQ' in filtered_df.columns:
                moq_medio = filtered_df['MOQ'].mean()
                st.metric("📋 MOQ Médio", f"{moq_medio:.0f}")
        
        # Show distribution by supplier if available
        if 'UltimoFornecedor' in filtered_df.columns:
            st.subheader("🏭 Distribuição por Fornecedor")
            
            supplier_counts = filtered_df['UltimoFornecedor'].value_counts()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(supplier_counts.head(10))
            
            with col2:
                st.dataframe(
                    supplier_counts.reset_index().rename(columns={'index': 'Fornecedor', 'UltimoFornecedor': 'Produtos'}),
                    use_container_width=True
                )
    
    else:
        st.warning("🔍 Nenhum produto encontrado com os filtros aplicados") 