import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 網頁基本設定
st.set_page_config(page_title="ASRS 物流自動化評估系統", layout="wide")
st.title("📦 ASRS 自動化倉儲物流評估系統")
st.markdown("請上傳客戶的 Excel 原始數據，系統將自動分析 Active SKU 並規劃最佳儲存型式。")

# 2. 側邊欄：互動參數設定
st.sidebar.header("⚙️ ASRS 設備參數設定")
pallet_limit = st.sidebar.number_input("棧板最長邊限制 (cm)", value=120.0, step=10.0)
tote_l = st.sidebar.number_input("料箱長度上限 (cm)", value=55.0, step=5.0)
tote_w = st.sidebar.number_input("料箱寬度上限 (cm)", value=35.0, step=5.0)
tote_h = st.sidebar.number_input("料箱高度上限 (cm)", value=25.0, step=5.0)

# 3. 檔案上傳區
uploaded_file = st.file_uploader("上傳 Excel 檔案 (需包含 1_Item master 與 4_Outbound 工作表)", type=["xlsx"])

if uploaded_file:
    try:
        # 讀取 Excel 資料
        df_item = pd.read_excel(uploaded_file, sheet_name="1_Item master", header=1) 
        df_outbound = pd.read_excel(uploaded_file, sheet_name="4_Outbound", header=2)
        
        # 確保欄位名稱正確 (根據你的檔案結構可微調)
        df_item = df_item.rename(columns={'Product No.': 'Product_No', 'Length': 'L', 'Width': 'W', 'Height': 'H'})
        df_outbound = df_outbound.rename(columns={'Product No.': 'Product_No'})

        st.success("✅ 檔案讀取成功！開始執行分析...")

        # --- 步驟 1 & 2：篩選 Active SKU ---
        active_skus = df_outbound['Product_No'].dropna().unique()
        df_item['Status'] = df_item['Product_No'].apply(lambda x: 'Active' if x in active_skus else 'Discontinue')
        
        # 只保留 Active 的商品進行後續尺寸評估
        df_active = df_item[df_item['Status'] == 'Active'].copy()

        # --- 步驟 3 ~ 6：尺寸判斷與儲存分流 ---
        # 計算最長邊
        df_active['Max_Edge'] = df_active[['L', 'W', 'H']].max(axis=1)

        # 定義分類邏輯
        def classify_storage(row):
            if row['Max_Edge'] > pallet_limit:
                return 'Oversize (外場)'
            elif row['L'] <= tote_l and row['W'] <= tote_w and row['H'] <= tote_h:
                return '料箱 (Tote)'
            else:
                return '棧板 (Pallet)'

        df_active['Storage_Type'] = df_active.apply(classify_storage, axis=1)

        # --- 數據視覺化展示 ---
        st.divider()
        st.subheader("📊 系統分析結果")
        
        # KPI 數據卡片
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("總 SKU 數", len(df_item))
        col2.metric("Active SKU 數", len(df_active))
        
        tote_count = len(df_active[df_active['Storage_Type'] == '料箱 (Tote)'])
        oversize_count = len(df_active[df_active['Storage_Type'] == 'Oversize (外場)'])
        asrs_rate = round(((len(df_active) - oversize_count) / len(df_active)) * 100, 1) if len(df_active) > 0 else 0
        
        col3.metric("ASRS 可入庫率", f"{asrs_rate} %")
        col4.metric("料箱適合件數", tote_count)

        # 繪製圓餅圖
        st.subheader("📦 儲存型式分佈佔比")
        fig = px.pie(df_active, names='Storage_Type', hole=0.4, color='Storage_Type',
                     color_discrete_map={'料箱 (Tote)':'#2ecc71', '棧板 (Pallet)':'#3498db', 'Oversize (外場)':'#e74c3c'})
        st.plotly_chart(fig, use_container_width=True)

        # 顯示最終報表
        st.subheader("📋 最終分類明細表")
        display_columns = ['Product_No', 'Category or type', 'Status', 'L', 'W', 'H', 'Max_Edge', 'Storage_Type']
        st.dataframe(df_active[display_columns])

    except Exception as e:
        st.error(f"檔案解析發生錯誤，請確認上傳的 Excel 格式是否正確。詳細錯誤：{e}")