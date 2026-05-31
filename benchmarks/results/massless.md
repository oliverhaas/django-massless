# Benchmark report: massless
Config: C=50 N=10000 target=http://127.0.0.1:8000

## Framework-bound, no DB
### Root JSON Async (/)
  Reqs/sec     76210.94   20569.01   93164.23
  Latency      658.81us     1.20ms    28.56ms
  Latency Distribution
     50%   555.00us
     75%   596.00us
     90%   632.00us
     99%     1.19ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Root JSON Sync (/sync)
  Reqs/sec     98664.68    9469.35  110916.43
  Latency      513.18us   348.21us    12.20ms
  Latency Distribution
     50%   472.00us
     75%   515.00us
     90%   575.00us
     99%     0.95ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 10kb JSON Async (/10k-json)
  Reqs/sec     39053.93    2372.24   42408.14
  Latency        1.28ms   802.34us    26.58ms
  Latency Distribution
     50%     1.16ms
     75%     1.25ms
     90%     1.55ms
     99%     2.48ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### 10kb JSON Sync (/sync-10k-json)
  Reqs/sec    100054.50   11926.80  106505.81
  Latency      496.29us   283.25us    10.72ms
  Latency Distribution
     50%   466.00us
     75%   475.00us
     90%   554.00us
     99%     0.93ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1kb JSON (/1k-json)
  Reqs/sec    116905.86   44475.66  207209.07
  Latency      500.13us   240.91us     9.10ms
  Latency Distribution
     50%   469.00us
     75%   485.00us
     90%   574.00us
     99%     0.94ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 100kb JSON (/100k-json)
  Reqs/sec     98956.39    7017.62  106463.61
  Latency      501.32us   281.89us    10.77ms
  Latency Distribution
     50%   461.00us
     75%   494.00us
     90%   560.00us
     99%     0.93ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 500kb JSON (/500k-json)
  Reqs/sec     98913.17   11637.28  112389.68
  Latency      511.76us   410.98us    13.05ms
  Latency Distribution
     50%   475.00us
     75%   490.00us
     90%   551.00us
     99%     0.96ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### 1mb JSON (/1m-json)
  Reqs/sec     90383.97    7317.74   99308.89
  Latency      548.51us   300.86us    11.24ms
  Latency Distribution
     50%   522.00us
     75%   556.00us
     90%   590.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Path Param int (/items/12345)
  Reqs/sec     72625.13    6563.25   80327.84
  Latency      684.46us   378.30us    13.29ms
  Latency Distribution
     50%   660.00us
     75%   684.00us
     90%   707.00us
     99%     1.32ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Path + Query (/items/12345?q=hello)
  Reqs/sec     70770.54   10249.65   81924.16
  Latency      716.29us   663.33us    21.43ms
  Latency Distribution
     50%   663.00us
     75%   712.00us
     90%   772.00us
     99%     1.36ms
    1xx - 0, 2xx - 10000, 3xx - 0, 4xx - 0, 5xx - 0

### Typed Params (/bench/params/typed/12345?count=3&price=1.5&active=true)
  Reqs/sec     91856.70   10417.50  102836.25
  Latency      541.37us   339.41us    11.48ms
  Latency Distribution
     50%   513.00us
     75%   556.00us
     90%   582.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi Query (/bench/params/multi-query?page=2&limit=20&sort=id&order=asc&filter_active=true&min_price=1.0&max_price=9.0)
  Reqs/sec     86236.18    6060.29   95063.69
  Latency      577.21us   329.65us    11.00ms
  Latency Distribution
     50%   557.00us
     75%   579.00us
     90%   611.00us
     99%     1.10ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Header Param (/header)
  Reqs/sec     87355.87   10156.35   94522.03
  Latency      570.00us   357.89us    14.18ms
  Latency Distribution
     50%   530.00us
     75%   550.00us
     90%   580.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Cookie Param (/cookie)
  Reqs/sec     90196.49    6070.12   95262.88
  Latency      551.65us   313.69us    10.76ms
  Latency Distribution
     50%   530.00us
     75%   550.00us
     90%   573.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Exception 404 (/exc)
  Reqs/sec     95044.28    6601.15  103176.45
  Latency      520.64us   212.09us     7.60ms
  Latency Distribution
     50%   492.00us
     75%   542.00us
     90%   564.00us
     99%     1.01ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### HTML Response (/html)
  Reqs/sec     90665.40   10584.85  101112.26
  Latency      546.62us   165.62us     4.66ms
  Latency Distribution
     50%   515.00us
     75%   558.00us
     90%   628.00us
     99%     1.10ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Redirect 302 (/redirect)
  Reqs/sec     88771.39   11630.23  102881.24
  Latency      564.23us   355.02us    11.99ms
  Latency Distribution
     50%   535.00us
     75%   595.00us
     90%   650.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### JSON Parse/Validate (/bench/parse)
  Reqs/sec     84735.40    7036.80   92526.34
  Latency      585.92us   335.01us    12.32ms
  Latency Distribution
     50%   555.00us
     75%   579.00us
     90%   610.00us
     99%     1.11ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Form urlencoded (/form)
  Reqs/sec     84624.38    5337.99   89614.45
  Latency      585.44us   274.75us    10.72ms
  Latency Distribution
     50%   566.00us
     75%   581.00us
     90%   605.00us
     99%     1.12ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Raw (/bench/serializer-raw)
  Reqs/sec     88326.62    7405.93   96849.44
  Latency      558.73us   346.19us    11.29ms
  Latency Distribution
     50%   525.00us
     75%   559.00us
     90%   604.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Serializer Validated (/bench/serializer-validated)
  Reqs/sec     85686.26    8707.82   93884.64
  Latency      578.17us   335.77us    11.09ms
  Latency Distribution
     50%   529.00us
     75%   562.00us
     90%   664.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single Concrete (/bench/single)
  Reqs/sec     89862.99    5273.04   93850.01
  Latency      550.61us   328.26us    11.28ms
  Latency Distribution
     50%   528.00us
     75%   550.00us
     90%   566.00us
     99%     1.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union Single (/bench/union-single)
  Reqs/sec     90762.28    1942.98   92069.81
  Latency      546.20us   193.84us     8.08ms
  Latency Distribution
     50%   532.00us
     75%   546.00us
     90%   563.00us
     99%     1.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List Concrete (/bench/list)
  Reqs/sec     85568.81    4055.39   89088.71
  Latency      580.14us   320.42us    11.68ms
  Latency Distribution
     50%   565.00us
     75%   576.00us
     90%   590.00us
     99%     1.06ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Union List (/bench/union-list)
  Reqs/sec     90530.80    6094.03   96013.22
  Latency      548.73us   299.34us     9.96ms
  Latency Distribution
     50%   516.00us
     75%   546.00us
     90%   588.00us
     99%     1.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Post Branch (/feed/0)
  Reqs/sec     83768.16    6791.16   92628.95
  Latency      591.14us   184.24us     6.62ms
  Latency Distribution
     50%   545.00us
     75%   582.00us
     90%   691.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Comment Branch (/feed/1)
  Reqs/sec     89017.57    5638.23   96762.20
  Latency      556.76us   277.97us     9.78ms
  Latency Distribution
     50%   532.00us
     75%   550.00us
     90%   576.00us
     99%     1.07ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Like Branch (/feed/2)
  Reqs/sec     88076.21    6189.77   93775.10
  Latency      564.99us   359.54us    13.00ms
  Latency Distribution
     50%   547.00us
     75%   565.00us
     90%   578.00us
     99%     1.04ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Feed Mixed 100 (/feed)
  Reqs/sec     89690.65    5078.98   96166.48
  Latency      552.87us   344.08us    11.39ms
  Latency Distribution
     50%   531.00us
     75%   551.00us
     90%   568.00us
     99%     1.09ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Tuple (/bench/multi/tuple)
  Reqs/sec     88149.30    6893.16   93967.02
  Latency      564.44us   360.56us    11.99ms
  Latency Distribution
     50%   539.00us
     75%   560.00us
     90%   592.00us
     99%     1.08ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0

### Multi-Response Dict (/bench/multi/dict)
  Reqs/sec     88733.99    4339.89   90744.83
  Latency      558.51us   284.17us    10.81ms
  Latency Distribution
     50%   539.00us
     75%   556.00us
     90%   581.00us
     99%     1.05ms
    1xx - 0, 2xx - 0, 3xx - 0, 4xx - 10000, 5xx - 0
