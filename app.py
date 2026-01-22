import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px 
import io
# ==================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==================================================
st.set_page_config(page_title="SalesOps Manager v1.2", layout="wide")

# ==================================================
# 2. CONEXÃO COM O BANCO DE DADOS
# ==================================================

@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["dbname"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"]
    )

try:
    conn = init_connection()
except Exception as e:
    st.error(f"Erro ao conectar no banco: {e}")
    st.stop()

# ==================================================
# 3. INTERFACE PRINCIPAL E MENU
# ==================================================
st.title("🚀 SalesOps Manager v1.2")
st.markdown("---")

menu = st.sidebar.selectbox(
    "Navegação", 
    ["Dashboard", "Registrar Venda", "Cadastrar Produtos", "Gerenciar Vendas", "Banco de Dados"]
)

# ==================================================
# 📊 MENU: DASHBOARD (COM EXPORTAÇÃO EXCEL 📥)
# ==================================================
if menu == "Dashboard":
    st.subheader("📊 Painel de Vendas & Comissões")

    # Filtros de Data
    col_data1, col_data2 = st.columns(2)
    with col_data1:
        data_inicio = st.date_input("Data Início", pd.to_datetime("2000-01-01"))
    with col_data2:
        data_fim = st.date_input("Data Fim", pd.to_datetime("today"))

    query = f"""
    SELECT 
        v.id_venda,
        v.valor_total,
        v.quantidade,
        v.data_venda,
        ven.nome as vendedor,
        ven.comissao_percentual,
        p.nome_produto
    FROM vendas v
    JOIN vendedores ven ON v.id_vendedor = ven.id_vendedor
    JOIN produtos p ON v.id_produto = p.id_produto
    WHERE v.data_venda BETWEEN '{data_inicio}' AND '{data_fim}'
    """
    
    try:
        df_vendas = pd.read_sql(query, conn)
        
        if df_vendas.empty:
            st.warning("⚠️ Nenhuma venda encontrada neste período.")
        else:
            # Tratamento de dados
            df_vendas["comissao_percentual"] = pd.to_numeric(df_vendas["comissao_percentual"])
            df_vendas["valor_total"] = pd.to_numeric(df_vendas["valor_total"])
            df_vendas["quantidade"] = pd.to_numeric(df_vendas["quantidade"])
            df_vendas["comissao_valor"] = df_vendas["valor_total"] * (df_vendas["comissao_percentual"] / 100)
            
            # KPIs
            total_vendido = df_vendas["valor_total"].sum()
            total_comissao = df_vendas["comissao_valor"].sum()
            qtd_vendas = df_vendas.shape[0]
            
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Faturamento Total", f"R$ {total_vendido:,.2f}")
            col2.metric("💸 Comissões a Pagar", f"R$ {total_comissao:,.2f}")
            col3.metric("🧾 Total de Transações", qtd_vendas)
            
            st.markdown("---")

            # Meta Mensal
            meta_mensal = 50000.00
            percentual_meta = total_vendido / meta_mensal
            barra_visual = min(percentual_meta, 1.0) 

            st.write(f"### 🎯 Meta do Mês: R$ {meta_mensal:,.2f}")
            if total_vendido >= meta_mensal:
                st.success(f"🎉 PARABÉNS! META BATIDA! ({percentual_meta*100:.1f}%)")
                st.progress(1.0)
            else:
                st.progress(barra_visual)
                st.caption(f"🚀 Faltam R$ {meta_mensal - total_vendido:,.2f} ({percentual_meta*100:.1f}%)")

            st.markdown("---")
            
            # Gráficos Linha 1
            col_graf1, col_graf2 = st.columns(2)
            with col_graf1:
                st.caption("🤑 Ranking de Comissões")
                ranking_comissao = df_vendas.groupby("vendedor")["comissao_valor"].sum().reset_index()
                fig_comissao = px.bar(ranking_comissao, x="comissao_valor", y="vendedor", orientation='h', text_auto=True, color="comissao_valor", color_continuous_scale="Greens", title="Quem recebe mais?")
                st.plotly_chart(fig_comissao, use_container_width=True)
                
            with col_graf2:
                st.caption("📅 Faturamento Diário")
                timeline = df_vendas.groupby("data_venda")["valor_total"].sum().reset_index()
                fig_time = px.line(timeline, x="data_venda", y="valor_total", markers=True, title="Evolução Temporal")
                st.plotly_chart(fig_time, use_container_width=True)

            st.markdown("---")

            # Gráficos Linha 2
            st.subheader("🛒 Mix de Produtos (Market Share)")
            col_prod1, col_prod2 = st.columns(2)

            with col_prod1:
                st.caption("🏆 Faturamento por Produto (R$)")
                ranking_produtos = df_vendas.groupby("nome_produto")["valor_total"].sum().reset_index()
                fig_prod_faturamento = px.pie(ranking_produtos, values='valor_total', names='nome_produto', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu, title="Onde está o dinheiro?")
                fig_prod_faturamento.update_traces(textinfo='percent+label') 
                st.plotly_chart(fig_prod_faturamento, use_container_width=True)

            with col_prod2:
                st.caption("📊 Volume de Peças Vendidas (Unidades)")
                qtd_produtos = df_vendas.groupby("nome_produto")["quantidade"].sum().reset_index()
                fig_prod_qtd = px.pie(qtd_produtos, values='quantidade', names='nome_produto', hole=0.4, color_discrete_sequence=px.colors.sequential.Viridis, title="O que mais sai do estoque?")
                fig_prod_qtd.update_traces(textinfo='value')
                st.plotly_chart(fig_prod_qtd, use_container_width=True)

            # --- AQUI ESTÁ A NOVIDADE: TABELA + BOTÃO DE EXCEL ---
            with st.expander("🔎 Ver Relatório Detalhado"):
                 st.dataframe(df_vendas, use_container_width=True)
                 
                 # Lógica de Exportação
                 st.write("### 📥 Exportar Dados")
                 
                 # Cria um buffer de memória (arquivo virtual)
                 buffer = io.BytesIO()
                 
                 # Escreve o DataFrame nesse buffer usando engine do Excel
                 with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                     df_vendas.to_excel(writer, index=False, sheet_name='Vendas')
                 
                 # Prepara o botão de download
                 st.download_button(
                     label="Baixar Planilha Excel (.xlsx)",
                     data=buffer,
                     file_name="relatorio_vendas.xlsx",
                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                 )

    except Exception as e:
        st.error(f"Erro na conexão: {e}")       


# ==================================================
# 💰 MENU: REGISTRAR VENDA
# ==================================================
elif menu == "Registrar Venda":
    st.subheader("💰 Registrar Nova Venda")
    
    # Carrega dados para os selects
    vendedores = pd.read_sql("SELECT id_vendedor, nome FROM vendedores", conn)
    produtos = pd.read_sql("SELECT id_produto, nome_produto, preco_venda FROM produtos", conn)
    
    with st.form("form_venda"):
        vendedor_selecionado = st.selectbox("Vendedor:", vendedores["nome"])
        produto_selecionado = st.selectbox("Produto:", produtos["nome_produto"])
        quantidade = st.number_input("Quantidade:", min_value=1, step=1)
        botao_submit = st.form_submit_button("Confirmar Venda")

    if botao_submit:
        try:
            # Pega IDs
            id_vendedor = int(vendedores[vendedores["nome"] == vendedor_selecionado]["id_vendedor"].values[0])
            
            linha_produto = produtos[produtos["nome_produto"] == produto_selecionado].iloc[0]
            id_produto = int(linha_produto["id_produto"])
            preco = float(linha_produto["preco_venda"])
            
            total = preco * quantidade
            
            cur = conn.cursor()
            
            # Verifica Estoque
            cur.execute("SELECT estoque_atual FROM produtos WHERE id_produto = %s", (id_produto,))
            resultado = cur.fetchone()
            estoque_disponivel = resultado[0] if resultado else 0
            
            if estoque_disponivel < quantidade:
                st.error(f"❌ Estoque insuficiente! Restam apenas {estoque_disponivel}.")
            else:
                # Registra Venda
                cur.execute("""
                    INSERT INTO vendas (id_vendedor, id_produto, quantidade, valor_total)
                    VALUES (%s, %s, %s, %s)
                """, (id_vendedor, id_produto, quantidade, total))
                
                # Baixa Estoque
                novo_estoque = estoque_disponivel - quantidade
                cur.execute("UPDATE produtos SET estoque_atual = %s WHERE id_produto = %s", (novo_estoque, id_produto))
                
                conn.commit()
                st.success(f"✅ Venda Feita! Comissão gerada para {vendedor_selecionado}.")
            
            cur.close()
            
        except Exception as e:
            conn.rollback()
            st.error(f"Erro: {e}")


# ==================================================
# 📦 MENU: CONTROLE DE ESTOQUE (CADASTRAR E REPOR)
# ==================================================
# ATENÇÃO: Se quiser, pode mudar o nome no menu lateral lá em cima para "Controle de Estoque"
elif menu == "Cadastrar Produtos": 
    st.subheader("📦 Controle de Estoque")

    # Cria duas abas para organizar a tela
    aba1, aba2 = st.tabs(["🆕 Cadastrar Novo Produto", "➕ Repor Estoque Existente"])

    # ---------------------------------------------------------
    # ABA 1: CADASTRAR PRODUTO NOVO (O que já tínhamos)
    # ---------------------------------------------------------
    with aba1:
        st.write("### Cadastrar item que nunca foi vendido")
        with st.form("form_produto"):
            col_nome, col_cat = st.columns(2)
            
            with col_nome:
                novo_nome = st.text_input("Nome do Produto (Ex: Mouse Gamer)")
            with col_cat:
                opcoes_categorias = ["Periféricos", "Hardware", "Software", "Acessórios", "Serviços", "Outros"]
                nova_categoria = st.selectbox("Categoria:", opcoes_categorias)
                
            col_preco, col_estoque = st.columns(2)
            with col_preco:
                novo_preco = st.number_input("Preço de Venda (R$)", min_value=0.01, format="%.2f")
            with col_estoque:
                novo_estoque = st.number_input("Estoque Inicial:", min_value=1, step=1, value=10)
            
            btn_cadastrar = st.form_submit_button("Salvar Novo Produto")
        
        if btn_cadastrar:
            if not novo_nome:
                st.warning("⚠️ O nome do produto é obrigatório!")
            else:
                try:
                    cur = conn.cursor()
                    # Verifica duplicidade
                    cur.execute("SELECT id_produto FROM produtos WHERE nome_produto ILIKE %s", (novo_nome,))
                    if cur.fetchone():
                        st.error(f"❌ O produto '{novo_nome}' já existe! Vá na aba 'Repor Estoque' para adicionar mais.")
                    else:
                        cur.execute("""
                            INSERT INTO produtos (nome_produto, preco_venda, estoque_atual, categoria)
                            VALUES (%s, %s, %s, %s)
                        """, (novo_nome, novo_preco, novo_estoque, nova_categoria))
                        conn.commit()
                        st.success(f"✅ Produto '{novo_nome}' criado com sucesso!")
                    cur.close()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Erro: {e}")

    # ---------------------------------------------------------
    # ABA 2: REPOR ESTOQUE (NOVO!!!)
    # ---------------------------------------------------------
    with aba2:
        st.write("### Adicionar unidades a um produto já existente")
        
        # Busca produtos para o selectbox
        df_prods = pd.read_sql("SELECT id_produto, nome_produto, estoque_atual FROM produtos ORDER BY nome_produto", conn)
        
        col_sel_prod, col_qtd_add = st.columns([3, 1])
        
        with col_sel_prod:
            # Selectbox para escolher o produto
            prod_opcao = st.selectbox("Escolha o Produto para Repor:", df_prods["nome_produto"])
        
        # Pega a quantidade atual do produto selecionado para mostrar pro usuário
        qtd_atual = df_prods[df_prods["nome_produto"] == prod_opcao]["estoque_atual"].values[0]
        
        with col_qtd_add:
            st.metric("Estoque Atual", f"{qtd_atual} un.")

        # Formulário de Reposição
        with st.form("form_reposicao"):
            qtd_entrada = st.number_input(f"Quantas unidades de '{prod_opcao}' chegaram?", min_value=1, step=1)
            btn_repor = st.form_submit_button("🔄 Atualizar Estoque")
            
        if btn_repor:
            try:
                # Pega o ID do produto selecionado
                id_prod_repor = int(df_prods[df_prods["nome_produto"] == prod_opcao]["id_produto"].values[0])
                
                cur = conn.cursor()
                # Soma o estoque antigo + entrada
                novo_total = int(qtd_atual + qtd_entrada)
                
                cur.execute("UPDATE produtos SET estoque_atual = %s WHERE id_produto = %s", (novo_total, id_prod_repor))
                conn.commit()
                cur.close()
                
                st.success(f"✅ Estoque atualizado! '{prod_opcao}' passou de {qtd_atual} para {novo_total} unidades.")
                # Dica: Botão para forçar atualização da página e mostrar o número novo
                if st.button("Atualizar Página"): 
                    st.rerun()
                    
            except Exception as e:
                conn.rollback()
                st.error(f"Erro ao repor: {e}")

    st.markdown("---")
    st.write("### 📋 Visão Geral do Estoque")
    # Mostra tabela completa para conferência
    df_estoque = pd.read_sql("SELECT id_produto, nome_produto, categoria, estoque_atual, preco_venda FROM produtos ORDER BY estoque_atual ASC", conn)
    
    # Destaque visual: Produtos com pouco estoque aparecem primeiro (ORDER BY ASC)
    st.dataframe(df_estoque, use_container_width=True)


# ==================================================
# ⚙️ MENU: GERENCIAR VENDAS (CRUD)
# ==================================================
elif menu == "Gerenciar Vendas":
    st.subheader("⚙️ Gerenciar Vendas (Editar ou Excluir)")
    
    df_vendas = pd.read_sql("SELECT * FROM vendas ORDER BY id_venda DESC", conn)
    st.dataframe(df_vendas, use_container_width=True)
    
    col_del, col_upd = st.columns(2)
    
    with col_del:
        st.error("🗑️ Área de Exclusão")
        id_del = st.number_input("ID para apagar:", min_value=1, step=1)
        if st.button("Apagar Venda"):
            if id_del in df_vendas['id_venda'].values:
                try:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM vendas WHERE id_venda = %s", (id_del,))
                    conn.commit()
                    cur.close()
                    st.success("Venda apagada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
            else:
                 st.warning("ID não encontrado")

    with col_upd:
        st.warning("✏️ Área de Edição (Quantidade)")
        id_edit = st.number_input("ID para editar:", min_value=1, step=1)
        nova_qtd = st.number_input("Nova Quantidade:", min_value=1, step=1)
        if st.button("Atualizar"):
             if id_edit in df_vendas['id_venda'].values:
                try:
                    cur = conn.cursor()
                    # Busca preço atual para recalcular total
                    cur.execute("SELECT preco_venda FROM produtos p JOIN vendas v ON p.id_produto = v.id_produto WHERE v.id_venda = %s", (id_edit,))
                    preco = cur.fetchone()[0]
                    novo_total = float(preco) * nova_qtd
                    
                    cur.execute("UPDATE vendas SET quantidade = %s, valor_total = %s WHERE id_venda = %s", (nova_qtd, novo_total, id_edit))
                    conn.commit()
                    cur.close()
                    st.success("Atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")


