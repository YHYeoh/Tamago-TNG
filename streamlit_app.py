import streamlit as st
import tabula
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit_shadcn_ui as ui

class Tamago:

    def __init__(self):
        self.ui = st
        self.ui.image('./header.jpeg', use_column_width=True, clamp=True)
        self.ui.title("Tamago - たまご")
        self.ui.header("Your Personal Financial Assistant")
        self.ui.write("Tamago helps you to analyze your **TouchNGo** transaction records. Let's get started!")
        self.upload()
        return
    
    def help(self):
        with self.ui.expander("How to use?"):
            self.ui.write("Download your TouchNGo transaction records from the TouchNGo app")
            self.ui.caption("Currently only support filtered results (at lease one filter selected)")
            self.ui.image("https://tngdigitalhelp1570521917.zendesk.com/hc/article_attachments/1500011964482/mceclip1.png")
        
    def upload(self):
        self.help()
        self.ui.subheader("Upload your TouchNGo transaction records")
        self.file = self.ui.file_uploader('File uploader', accept_multiple_files=False, type=['pdf'])
        if self.file is not None:
            self.ui.success("File uploaded successfully!")
            self.process()
            self.export()
            self.filter()
            self.summary()
            self.dashboard()
        else:
            self.ui.warning("Please upload a file!")

    def export(self):
        data = self.df.to_csv(index=False)
        #get today's date
        today = pd.Timestamp("today").strftime("%Y-%m-%d")
        st.download_button('Download processed CSV', data, file_name="processed_{}.csv".format(today), mime="text/csv")

    def process(self):
        with self.ui.spinner("Processing your records..."):
            self.df = tabula.read_pdf(self.file, pages = "all", multiple_tables=False)[0]
            raw_df = self.df
            self.df.drop(['Status', "Wallet Balanc", "Details", "Reference"], axis=1, inplace=True)
            #filter out the Transaction Type with "Reload"
            self.df = self.df[self.df['Transaction Type'] != "Reload"]
            self.df = self.df[self.df['Transaction Type'] != "Receive from Wallet"]

            #Rename Transaction Type DuitNow QR TNGD to DuitNow QR
            self.df['Transaction Type'] = self.df['Transaction Type'].str.replace('DuitNow QR TNGD', 'DuitNow QR', regex=False)

            #transform the data in column "Date" to datetime format
            self.df['Date'] = pd.to_datetime(self.df['Date'], format ='mixed', dayfirst=True,)

            #transform the data in column "Description" to string format
            self.df['Description'] = self.df['Description'].astype(str)

            #Mappings the description to the correct description
            #create regex for string like "#h1zo-65mi"
            regex = r"#\w{4}-\w{4} null"
            #if description contains string like "#h1zo-65mi", replace it with"FoodPanda"
            self.df['Description'] = self.df['Description'].str.replace(regex, 'FoodPanda', regex=True)
            self.df['Description'] = self.df['Description'].str.replace('QLMAXINCOME SDN BHD', 'Family Mart', regex=False)

            #transform the data in the column (Amount (RM)) to float format, current format is RMx.xx
            self.df['Amount (RM)'] = self.df['Amount (RM)'].str.replace('RM', '').astype(np.float32).round(2)
            #transform the column Transaction Type to be categorical
            self.df['Transaction Type'] = self.df['Transaction Type'].astype('category')

            self.ui.success("Done!")
            self.ui.subheader("Your records")
            self.ui.write(raw_df.describe())
            self.ui.dataframe(self.df)

    def filter(self):
        self.ui.sidebar.subheader("Filter your records")
        self.ui.sidebar.write("Filters")
        #from date range
        self.start_date = self.ui.sidebar.date_input("From Date", self.df['Date'].min())
        #to date range
        self.end_date = self.ui.sidebar.date_input("To Date", self.df['Date'].max())

        #transaction type
        self.transaction_type = self.ui.sidebar.multiselect("Transaction Type", self.df["Transaction Type"].unique(), default=self.df["Transaction Type"].unique().tolist())

        #filter the data
        self.filtered_df = self.df[(self.df['Date'] >= self.start_date.strftime("%Y-%m-%d")) & (self.df['Date'] <= self.end_date.strftime("%Y-%m-%d"))]
        self.filtered_df = self.df[self.df['Transaction Type'].isin(self.transaction_type)]

        self.ui.subheader("Your filtered records")
        self.ui.dataframe(self.filtered_df)

    def summary(self):
        self.ui.subheader("Summary")
        cols = st.columns(3)
        with cols[0]:
            ui.metric_card(title="Total Amount (RM)", content=str(self.filtered_df['Amount (RM)'].sum()), key="card1")
        with cols[1]:
            ui.metric_card(title="Total Transactions", content=self.filtered_df.shape[0], key="card2")
        with cols[2]:
            ui.metric_card(title="Total Days", content=self.filtered_df['Date'].nunique(), key="card3")

        #breakdown to each transaction type
        cols = st.columns(3)
        for i in range(len(self.filtered_df['Transaction Type'].unique())):
            with cols[i]:
                ui.metric_card(title=self.filtered_df['Transaction Type'].unique()[i], content=self.filtered_df[self.filtered_df['Transaction Type'] == self.filtered_df['Transaction Type'].unique()[i]].shape[0], key="card4_{}".format(i))


    def dashboard(self):
        self.ui.subheader("Dashboard")
        df_grouped = self.filtered_df.groupby('Date').sum(numeric_only=True)
        df_grouped.reset_index(inplace=True)
        fig = go.Figure([go.Scatter(x=df_grouped['Date'], y=df_grouped['Amount (RM)'])])
        fig.update_layout(title='Transaction Amount against Date', xaxis_title='Date', yaxis_title='Amount (RM)')
        fig.update_traces(mode="markers+lines", hovertemplate=None)
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = go.Figure(data=[go.Pie(labels=self.filtered_df['Transaction Type'].unique(), values=self.filtered_df['Transaction Type'].value_counts())])
        fig.update_layout(title='Transaction Type')
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = go.Figure([go.Bar(x=self.filtered_df['Transaction Type'].unique(), y=self.filtered_df['Amount (RM)'].groupby(self.filtered_df['Transaction Type']).sum())])
        fig.update_layout(title='Total Amount for each Transaction Type', xaxis_title='Transaction Type', yaxis_title='Amount (RM)')
        self.ui.plotly_chart(fig, use_container_width=True)

        df_pivot = self.filtered_df.pivot_table(index='Date', columns='Transaction Type', values='Amount (RM)', aggfunc='sum')
        fig = go.Figure(data=go.Heatmap(
                        z=df_pivot,
                        x=df_pivot.columns,
                        y=df_pivot.index,
                        colorscale='Viridis'))
        fig.update_layout(title='Transaction Type against Date', xaxis_title='Transaction Type', yaxis_title='Date')
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = go.Figure(data=[
            go.Scatter(
                x=self.filtered_df['Description'],
                y=self.filtered_df['Amount (RM)'],
                mode='markers',
                marker=dict(
                    size=self.filtered_df['Amount (RM)'],
                    sizemode='area',
                    sizeref=2.*max(self.filtered_df['Amount (RM)'])/(40.**2),
                    sizemin=4
                )
            )
        ])
        fig.update_layout(title='Spending by Description', xaxis_title='Description', yaxis_title='Amount (RM)')
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = px.histogram(self.filtered_df, x="Amount (RM)", nbins=20, title="Histogram of Amount (RM)")
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = px.box(self.filtered_df, x="Transaction Type", y="Amount (RM)", title="Boxplot of Transaction Type against Amount (RM)")
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = go.Figure(data=[go.Scatter3d(
        x=self.filtered_df['Date'],
        y=self.filtered_df['Transaction Type'],
        z=self.filtered_df['Amount (RM)'],
        mode='markers',
        marker=dict(
            size=8,
            color=self.filtered_df['Amount (RM)'],
            colorscale='Viridis',
        )
        )])
        fig.update_layout(scene=dict(xaxis_title='Date', yaxis_title='Transaction Type', zaxis_title='Amount (RM)'))
        self.ui.plotly_chart(fig, use_container_width=True)

        fig = px.line(self.filtered_df, x='Date', y='Amount (RM)', title='Spending Trends Over Time')
        fig.update_xaxes(rangeselector=dict(buttons=list([
            dict(count=1, label="1m", step="month", stepmode="backward"),
            dict(count=6, label="6m", step="month", stepmode="backward"),
            dict(count=1, label="YTD", step="year", stepmode="todate"),
            dict(count=1, label="1y", step="year", stepmode="backward"),
            dict(step="all")
        ])))
        self.ui.plotly_chart(fig, use_container_width=True)


        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.filtered_df['Date'], y=self.filtered_df['Amount (RM)'].cumsum(), fill='tozeroy', mode='lines'))
        fig.update_layout(title='Cumulative Spending', xaxis_title='Date', yaxis_title='Amount (RM)')
        self.ui.plotly_chart(fig, use_container_width=True)

        self.filtered_df['Month'] = self.filtered_df['Date'].dt.month
        fig = px.bar(self.filtered_df, x='Date', y='Amount (RM)', color='Transaction Type', title='Total Spent Per Transaction Type by Month')
        self.ui.plotly_chart(fig, use_container_width=True)

        return
    

if __name__ == "__main__":
    tamago = Tamago()
