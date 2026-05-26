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
        # --- 1. 讀取 1_Item master 並進行清洗 ---
        df_item_raw = pd.read_excel(uploaded_file, sheet_name="1_Item master", header=None)
        
        # 自動尋找含有 "Product No." 關鍵字的那一列作為標頭起點
        item_header_row = df_item_raw[df_item_raw.astype(str).apply(lambda r: r.str.contains("Product No.", na=False)).any(axis=1)].index[0]
        
        # 依據固定的相對位置提取資料，徹底解決雙層標頭與合併儲存格問題
        df_item = pd.DataFrame()
        df_item['Product_No'] = df_item_raw.iloc[item_header_row+2:, 0].astype(str).str.strip() # 往下兩列是實體資料
        df_item['Category'] = df_item_raw.iloc[item_header_row+2:, 1]
        df_item['L'] = pd.to_numeric(df_item_raw.iloc[item_header_row+2:, 7], errors='coerce')   # 產品尺寸-長(第8欄)
        df_item['W'] = pd.to_numeric(df_item_raw.iloc[item_header_row+2:, 8], errors='coerce')   # 產品尺寸-寬(第9欄)
        df_item['H'] = pd.to_numeric(df_item_raw.iloc[item_header_row+2:, 9], errors='coerce')   # 產品尺寸-高(第10欄)
        df_item['Weight'] = pd.to_numeric(df_item_raw.iloc[item_header_row+2:, 10], errors='coerce') # 重量
        
        # 過濾掉品項編號為空值的無效列
        df_item = df_item[df_item['Product_No'].notna() & (df_item['Product_No'] != 'nan') & (df_item['Product_No'] != '')]

        # --- 2. 讀取 4_Outbound 並提取 Active SKU ---
        df_out_raw = pd.read_excel(uploaded_file, sheet_name="4_Outbound", header=None)
        out_header_row = df_out_raw[df_out_raw.astype(str).apply(lambda r: r.str.contains("Product No.", na=False)).any(axis=1)].index[0]
        
        df_outbound = pd.DataFrame()
        df_outbound['Product_No'] = df_out_raw.iloc[out_header_row+1:, 2].astype(str).str.strip() # 第三欄是 Product No.
        active_skus = df_outbound['Product_No'].dropna().unique()

        st.success("✅ 檔案讀取與欄位清洗成功！")

        # --- 3. 執行物流評估邏輯 ---
        df_item['Status'] = df_item['Product_No'].apply(lambda x: 'Active' if x in active_skus else 'Discontinue')
        df_active = df_item[df_item['Status'] == 'Active'].copy()

        if not df_active.empty:
            # 計算商品最長邊
            df_active['Max_Edge'] = df_active[['L', 'W', 'H']].max(axis=1)

            # 儲存型式分流分類
            def classify_storage(row):
                if pd.isna(row['Max_Edge']) or row['Max_Edge'] == 0:
                    return '尺寸資料不全'
                elif row['Max_Edge'] > pallet_limit:
                    return 'Oversize (外場)'
                elif row['L'] <= tote_l and row['W'] <= tote_w and row['H'] <= tote_h:
                    return '料箱 (Tote)'
                else:
                    return '棧板 (Pallet)'

            df_active['Storage_Type'] = df_active.apply(classify_storage, axis=1)

            # --- 4. 數據視覺化看板展示 ---
            st.divider()
            st.subheader("📊 系統分析結果")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("總 SKU 數", len(df_item))
            col2.metric("Active SKU 數", len(df_active))
            
            tote_count = len(df_active[df_active['Storage_Type'] == '料箱 (Tote)'])
            oversize_count = len(df_active[df_active['Storage_Type'] == 'Oversize (外場)'])
            asrs_rate = round(((len(df_active) - oversize_count) / len(df_active)) * 100, 1) if len(df_active) > 0 else 0
            
            col3.metric("ASRS 可入庫率", f"{asrs_rate} %")
            col4.metric("料箱適合件數", tote_count)

            # 圓餅圖
            st.subheader("📦 儲存型式分佈佔比")
            fig = px.pie(df_active, names='Storage_Type', hole=0.4, color='Storage_Type',
                         color_discrete_map={'料箱 (Tote)':'#2ecc71', '棧板 (Pallet)':'#3498db', 'Oversize (外場)':'#e74c3c', '尺寸資料不全':'#7f8c8d'})
            st.plotly_chart(fig, use_container_width=True)

            # 詳細明細表
            st.subheader("📋 最終分類明細表")
            display_cols = ['Product_No', 'Category', 'Status', 'L', 'W', 'H', 'Max_Edge', 'Storage_Type']
            st.dataframe(df_active[display_cols])
        else:
            st.warning("⚠️ 讀取成功，但在出貨明細（4_Outbound）中沒有找到與主檔相符的商品編號，請確認數據內容。")

    except Exception as e:
        st.error(f"檔案解析發生錯誤，請確認上傳的 Excel 結構是否符合規範。詳細錯誤訊息：{e}")
