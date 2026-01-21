# 4.1.1 Implementasi Arsitektur Sistem

Arsitektur sistem yang telah dirancang pada Bab III subbab 3.7 telah diimplementasikan sepenuhnya dengan menggunakan pendekatan *layered architecture* dan sistem modular. Implementasi ini merealisasikan desain sistem yang terdiri dari enam layer utama, yaitu *User Interface Layer*, *Application Layer*, *Engine Layer*, *Core Layer*, *Data Source Layer*, dan *Storage Layer*. Setiap layer diimplementasikan sebagai modul independen yang memiliki tanggung jawab spesifik dan berinteraksi melalui antarmuka yang telah didefinisikan. Pendekatan modular ini memungkinkan pemisahan yang jelas antara logika bisnis, pemrosesan data, dan presentasi, sehingga sistem dapat dikembangkan dan dipelihara dengan lebih terstruktur.

Implementasi arsitektur mengikuti prinsip *separation of concerns* yang telah ditetapkan pada fase perancangan. Setiap layer berkomunikasi hanya dengan layer yang berdekatan, membentuk hierarki yang jelas dari layer presentasi hingga layer persistensi data. Aliran data dalam sistem dimulai dari *Data Source Layer* yang mengambil data pasar, diproses oleh *Core Layer* untuk perhitungan indikator teknikal, dievaluasi oleh *Engine Layer* untuk menghasilkan sinyal, dikoordinasikan oleh *Application Layer*, dan akhirnya ditampilkan melalui *User Interface Layer*. Struktur ini konsisten dengan rancangan arsitektur sistem yang telah dijelaskan pada Bab III.

## Implementasi User Interface Layer

*User Interface Layer* diimplementasikan sebagai antarmuka desktop yang menyediakan akses kepada pengguna untuk berinteraksi dengan sistem. Layer ini bertanggung jawab untuk menampilkan formulir konfigurasi aturan trading, daftar simbol saham yang dipantau (*watchlist*), kontrol operasional engine, serta visualisasi sinyal trading secara real-time. Implementasi menggunakan teknologi web standar yang ditampilkan dalam window desktop, memungkinkan pengembangan antarmuka yang responsif dengan tingkat kompleksitas yang terkendali. Layer ini berkomunikasi dengan *Application Layer* melalui protokol REST API untuk operasi data dan WebSocket untuk pembaruan real-time, sesuai dengan rancangan arsitektur yang telah ditetapkan.

Interaksi pengguna pada layer ini mencakup pembuatan dan pengelolaan aturan trading, pengaturan simbol saham yang akan dipantau, serta kontrol untuk memulai dan menghentikan proses analisis. Setiap aksi pengguna diterjemahkan menjadi permintaan ke *Application Layer* yang kemudian diteruskan ke layer yang sesuai untuk diproses. Hasil pemrosesan, baik berupa konfirmasi operasi maupun sinyal trading, dikembalikan ke layer ini untuk ditampilkan kepada pengguna. Desain ini memastikan bahwa layer presentasi tetap terpisah dari logika bisnis sistem.

## Implementasi Application Layer

*Application Layer* diimplementasikan sebagai layer orkestrasi yang mengoordinasikan seluruh operasi sistem. Layer ini menyediakan REST API untuk operasi CRUD (*Create, Read, Update, Delete*) terhadap aturan trading dan watchlist, serta endpoint untuk kontrol engine. Selain itu, layer ini mengimplementasikan mekanisme WebSocket untuk broadcasting sinyal trading secara real-time kepada *User Interface Layer*. Implementasi REST API mengikuti standar HTTP dan struktur endpoint yang konsisten, memfasilitasi komunikasi yang terstandarisasi antara frontend dan backend sistem.

Koordinasi antar-engine dilakukan oleh komponen orkestrasi pada layer ini, yang mengatur alur kerja dari berbagai mode operasi sistem seperti *scalping real-time*, *backtesting*, dan *screening*. Ketika pengguna memulai operasi melalui *User Interface Layer*, *Application Layer* bertanggung jawab untuk menginisialisasi *Engine Layer* yang sesuai, menyediakan konfigurasi yang diperlukan dari *Storage Layer*, dan memastikan aliran data berjalan dengan benar. Layer ini juga menangani pengelolaan state aplikasi dan memastikan sinkronisasi antara berbagai komponen sistem.

**Potongan Kode 4.1**  
*Contoh implementasi endpoint API untuk manajemen aturan trading*

```python
class RuleCreate(BaseModel):
    """Model untuk pembuatan aturan baru."""
    name: str
    definition: Dict[str, Any]
    mode: str

@signalgen_app.post("/api/rules/", status_code=status.HTTP_201_CREATED)
async def create_rule(rule: RuleCreate) -> Dict[str, Any]:
    """Endpoint untuk membuat aturan trading baru."""
    rule_id = repository.create_rule(
        name=rule.name,
        definition=rule.definition,
        mode=rule.mode
    )
    return {
        "id": rule_id,
        "name": rule.name,
        "created_at": datetime.now().isoformat()
    }
```

Potongan kode di atas menunjukkan bagaimana *Application Layer* menangani permintaan pembuatan aturan trading dari pengguna. Endpoint menerima data aturan dalam format terstruktur, melakukan validasi melalui model Pydantic, kemudian meneruskan ke *Storage Layer* untuk persistensi. Respons dikembalikan dalam format JSON standar yang dapat diproses oleh *User Interface Layer*. Implementasi ini mencerminkan arsitektur REST yang telah dirancang untuk komunikasi antar-layer.

## Implementasi Engine Layer

*Engine Layer* diimplementasikan sebagai layer yang bertanggung jawab untuk eksekusi logika analisis sesuai dengan mode operasi sistem. Terdapat tiga engine utama yang diimplementasikan, yaitu *Scalping Engine* untuk analisis real-time, *Backtesting Engine* untuk simulasi strategi historis, dan *Swing Screening Engine* untuk screening saham dalam jumlah besar. Setiap engine beroperasi secara independen dan dikoordinasikan oleh *Application Layer* sesuai dengan mode yang dipilih pengguna.

*Scalping Engine* mengintegrasikan komponen-komponen dari *Core Layer* untuk melakukan analisis secara berkelanjutan terhadap data pasar yang masuk. Engine ini menerima data tick atau bar dari *Data Source Layer*, meneruskannya ke *Core Layer* untuk perhitungan indikator, kemudian mengevaluasi hasil perhitungan tersebut terhadap aturan trading yang aktif. Ketika kondisi aturan terpenuhi, engine menghasilkan sinyal trading yang kemudian disimpan ke *Storage Layer* dan dibroadcast melalui *Application Layer* ke pengguna. Implementasi engine ini menggunakan pendekatan event-driven yang memungkinkan respons cepat terhadap perubahan kondisi pasar.

**Potongan Kode 4.2**  
*Contoh implementasi alur pemrosesan data dalam Scalping Engine*

```python
async def on_bar_update(self, bars: BarDataList, contract: Contract):
    """Callback untuk pembaruan bar data dari sumber data."""
    symbol = contract.symbol
    
    for bar in bars:
        tick_data = {
            'timestamp': bar.date,
            'price': bar.close,
            'volume': bar.volume
        }
        
        self.indicator_engine.add_tick(symbol, tick_data)
        indicator_values = self.indicator_engine.get_indicator_values(symbol)
        
        if self.active_rule and indicator_values:
            signal = self.rule_engine.evaluate(self.active_rule, indicator_values)
            if signal:
                await self.emit_signal(symbol, signal, indicator_values)
```

Potongan kode di atas mengilustrasikan bagaimana *Scalping Engine* memproses pembaruan data pasar. Setiap pembaruan data diteruskan ke *Indicator Engine* untuk perhitungan indikator, hasil perhitungan kemudian dievaluasi oleh *Rule Engine* untuk menentukan apakah sinyal trading harus dihasilkan. Alur ini mencerminkan arsitektur pipeline yang telah dirancang untuk pemrosesan data secara efisien.

## Implementasi Core Layer

*Core Layer* diimplementasikan sebagai inti dari sistem yang berisi logika bisnis utama untuk perhitungan indikator teknikal dan evaluasi aturan trading. Layer ini terdiri dari tiga komponen utama: *Indicator Engine* untuk perhitungan indikator teknikal, *Rule Engine* untuk evaluasi aturan trading, dan *Candle Builder* untuk agregasi data tick menjadi candle. Setiap komponen diimplementasikan sebagai modul independen yang dapat digunakan kembali oleh berbagai engine pada *Engine Layer*.

*Indicator Engine* bertanggung jawab untuk menghitung berbagai indikator teknikal seperti Moving Average, MACD, RSI, ADX, dan Bollinger Bands berdasarkan data candle yang tersedia. Implementasi menggunakan library teknikal yang telah tervalidasi untuk memastikan akurasi perhitungan. Engine ini mengelola riwayat data yang diperlukan untuk perhitungan indikator dengan periode panjang, serta menyediakan nilai indikator terkini dan nilai sebelumnya yang diperlukan untuk deteksi crossover. *Rule Engine* mengimplementasikan logika evaluasi aturan trading secara deterministik tanpa menggunakan eksekusi kode dinamis, mendukung operator perbandingan dan operator khusus seperti *cross up* dan *cross down*. Kedua komponen ini bekerja sama untuk menyediakan dasar evaluasi sinyal trading yang akurat dan konsisten.

**Potongan Kode 4.3**  
*Contoh implementasi evaluasi kondisi aturan trading*

```python
def evaluate_condition(self, condition: Dict, indicator_values: Dict) -> bool:
    """Evaluasi kondisi tunggal terhadap nilai indikator."""
    operand_a = condition['operandA']
    operator = condition['operator']
    operand_b = condition['operandB']
    
    value_a = self._get_operand_value(operand_a, indicator_values)
    value_b = self._get_operand_value(operand_b, indicator_values)
    
    if operator == '>':
        return value_a > value_b
    elif operator == '>=':
        return value_a >= value_b
    elif operator == '<':
        return value_a < value_b
    elif operator == '<=':
        return value_a <= value_b
    
    return False
```

Potongan kode di atas menunjukkan implementasi evaluasi kondisi aturan dalam *Rule Engine*. Setiap kondisi dievaluasi dengan membandingkan nilai operand yang diambil dari hasil perhitungan indikator. Pendekatan deterministik ini memastikan evaluasi yang aman tanpa risiko eksekusi kode yang tidak terprediksi, sesuai dengan prinsip keamanan yang ditetapkan dalam perancangan sistem.

## Implementasi Data Source Layer

*Data Source Layer* diimplementasikan sebagai layer abstraksi untuk akuisisi data pasar dari berbagai sumber. Layer ini menyediakan antarmuka standar yang memungkinkan sistem mengakses data dari berbagai provider tanpa mempengaruhi layer lain. Implementasi mencakup dua sumber data utama: sumber data real-time untuk operasi scalping dan sumber data historis untuk backtesting dan screening.

Setiap sumber data diimplementasikan sebagai kelas yang mengikuti kontrak antarmuka yang telah didefinisikan, menyediakan metode untuk pengambilan data historis dengan parameter simbol, rentang waktu, dan timeframe. Abstraksi ini memungkinkan penggantian atau penambahan sumber data baru tanpa perlu mengubah komponen lain dari sistem. Data yang dikembalikan oleh layer ini telah dinormalisasi ke dalam format standar OHLCV (*Open, High, Low, Close, Volume*) yang dapat langsung diproses oleh *Core Layer*. Implementasi juga mencakup penanganan error dan retry mechanism untuk memastikan ketersediaan data yang konsisten.

## Implementasi Storage Layer

*Storage Layer* diimplementasikan sebagai layer persistensi yang mengelola penyimpanan dan pengambilan data aplikasi. Layer ini bertanggung jawab untuk menyimpan konfigurasi aturan trading, daftar watchlist, riwayat sinyal trading, serta pengaturan sistem. Implementasi menggunakan database relasional dengan skema yang telah dirancang untuk mendukung operasi CRUD secara efisien.

Repositori database menyediakan metode-metode abstraksi untuk operasi data yang digunakan oleh *Application Layer* dan *Engine Layer*. Setiap tabel database didesain dengan normalisasi yang tepat untuk menghindari redundansi data sambil mempertahankan performa query. Implementasi mencakup mekanisme transaction management untuk memastikan konsistensi data, serta connection pooling untuk optimasi penggunaan resource. Layer ini juga menangani inisialisasi database dan migrasi skema jika diperlukan, memastikan struktur data selalu sesuai dengan kebutuhan sistem.

Interaksi antara berbagai layer dalam implementasi sistem mencerminkan rancangan arsitektur yang telah ditetapkan pada Bab III. Setiap layer berkomunikasi melalui antarmuka yang jelas dan terdefinisi dengan baik, memastikan coupling yang rendah antara komponen sistem. Modularitas ini memfasilitasi pengujian independen untuk setiap layer serta memudahkan proses pemeliharaan dan pengembangan lebih lanjut.

## Kesimpulan Implementasi

Implementasi arsitektur sistem telah merealisasikan seluruh rancangan yang ditetapkan pada Bab III dengan konsistensi penuh terhadap spesifikasi desain. Pendekatan *layered architecture* dan sistem modular yang diterapkan menghasilkan struktur kode yang terorganisir dengan baik, di mana setiap layer memiliki tanggung jawab yang jelas dan terdefinisi. Pemisahan antara *User Interface Layer*, *Application Layer*, *Engine Layer*, *Core Layer*, *Data Source Layer*, dan *Storage Layer* memungkinkan pengembangan dan pengujian yang independen untuk setiap komponen sistem.

Arsitektur yang telah diimplementasikan memastikan aliran data yang sistematis dari akuisisi data pasar hingga presentasi sinyal kepada pengguna, dengan setiap tahap pemrosesan ditangani oleh layer yang sesuai. Modularitas sistem juga memfasilitasi ekstensibilitas untuk penambahan fitur atau modifikasi komponen tanpa mempengaruhi bagian lain dari sistem. Implementasi ini menghasilkan sistem yang siap untuk diuji dan dievaluasi pada tahap selanjutnya, dengan fondasi arsitektur yang solid dan terstruktur untuk mendukung operasional sistem sinyal trading berbasis indikator teknikal.
