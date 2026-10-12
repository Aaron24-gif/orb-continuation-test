//+------------------------------------------------------------------+
//| M001_SlippageProbe.mq5                                           |
//| MEASUREMENT ONLY - it does not trade a strategy and has no edge.  |
//|                                                                  |
//| Each US cash-open day it places a minimum-size BUY STOP at the    |
//| 09:15-09:30 ET range high and a minimum-size SELL STOP at the low,|
//| valid until 09:45 ET. Anything that fills is CLOSED IMMEDIATELY   |
//| at market. Per fill it logs the stop level, the actual fill, the  |
//| delay, the spread, and the exit fill - i.e. entry slippage and    |
//| market-order exit slippage in the same minute.                    |
//|                                                                  |
//| Output (common files folder):                                     |
//|   m001_fills.csv  one row per fill                                |
//|   m001_days.csv   one row per day, including no-fill days         |
//| Sample floor before ANY conclusion: 60 fills (card M-001).        |
//+------------------------------------------------------------------+
#property strict
#include <Trade/Trade.mqh>

input int    MagicNumber        = 10012026;  // must differ from every other EA on the account
input int    ServerGMTOffsetHrs = 0;         // your server's offset from UTC (often +2/+3)
input int    RangeStartHourET   = 9;
input int    RangeStartMinET    = 15;
input int    RangeEndHourET     = 9;
input int    RangeEndMinET      = 30;
input int    CancelHourET       = 9;
input int    CancelMinET        = 45;
input double LotsOverride       = 0.0;       // 0 = use the symbol minimum
input bool   EnableTrading      = true;      // false = log levels only, place nothing

CTrade   trade;
datetime g_day_done = 0;                     // ET date whose orders are already placed
string   FILL_CSV   = "m001_fills.csv";
string   DAY_CSV    = "m001_days.csv";

//--- US DST: 2nd Sunday March 02:00 -> 1st Sunday November 02:00 local
bool IsUSDST(datetime utc)
{
   MqlDateTime t; TimeToStruct(utc, t);
   int y = t.year;
   datetime mar1 = StringToTime(StringFormat("%d.03.01 00:00", y));
   MqlDateTime m;  TimeToStruct(mar1, m);
   int shift     = (7 - m.day_of_week) % 7;
   datetime dst0 = mar1 + (shift + 7) * 86400 + 7 * 3600;   // 2nd Sun 02:00 EST = 07:00 UTC
   datetime nov1 = StringToTime(StringFormat("%d.11.01 00:00", y));
   MqlDateTime n;  TimeToStruct(nov1, n);
   int shift2    = (7 - n.day_of_week) % 7;
   datetime dst1 = nov1 + shift2 * 86400 + 6 * 3600;        // 1st Sun 02:00 EDT = 06:00 UTC
   return (utc >= dst0 && utc < dst1);
}

datetime ServerToUTC(datetime s) { return s - ServerGMTOffsetHrs * 3600; }
datetime UTCToServer(datetime u) { return u + ServerGMTOffsetHrs * 3600; }

//--- server time of today's ET hh:mm
datetime ETTimeToServer(datetime now_server, int hh, int mm)
{
   datetime utc = ServerToUTC(now_server);
   bool dst     = IsUSDST(utc);
   datetime et  = utc - (dst ? 4 : 5) * 3600;
   MqlDateTime e; TimeToStruct(et, e);
   e.hour = hh; e.min = mm; e.sec = 0;
   datetime et_target = StructToTime(e);
   return UTCToServer(et_target + (dst ? 4 : 5) * 3600);
}

datetime ETDate(datetime now_server)
{
   datetime utc = ServerToUTC(now_server);
   datetime et  = utc - (IsUSDST(utc) ? 4 : 5) * 3600;
   return et - (et % 86400);
}

double MinLot()
{
   if(LotsOverride > 0) return LotsOverride;
   return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
}

void Append(string file, string line)
{
   int h = FileOpen(file, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) { Print("M001: cannot open ", file, " err ", GetLastError()); return; }
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, line + "\r\n");
   FileClose(h);
}

void EnsureHeaders()
{
   if(!FileIsExist(FILL_CSV, FILE_COMMON))
      Append(FILL_CSV, "fill_time_server,symbol,side,stop_level,fill_price,slip_pts,delay_sec,"
                       "spread_at_fill_pts,exit_price,exit_slip_pts,volume,order_placed_server");
   if(!FileIsExist(DAY_CSV, FILE_COMMON))
      Append(DAY_CSV, "et_date,symbol,or_high,or_low,or_range_pts,placed,note");
}

//--- opening range from CLOSED M1 bars only
bool BuildRange(datetime now_server, double &or_h, double &or_l, string &note)
{
   datetime from = ETTimeToServer(now_server, RangeStartHourET, RangeStartMinET);
   datetime to   = ETTimeToServer(now_server, RangeEndHourET,   RangeEndMinET);
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, from, to - 60, r);
   if(n <= 0) { note = "no M1 bars in range window"; return false; }
   int expected = (int)((to - from) / 60);
   or_h = -DBL_MAX; or_l = DBL_MAX;
   for(int i = 0; i < n; i++) { or_h = MathMax(or_h, r[i].high); or_l = MathMin(or_l, r[i].low); }
   if(n < expected * 0.8) { note = StringFormat("only %d of %d range bars", n, expected); return false; }
   note = StringFormat("%d bars", n);
   return true;
}

int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   EnsureHeaders();
   PrintFormat("M001 probe on %s | min lot %.2f | trading=%s",
               _Symbol, MinLot(), EnableTrading ? "on" : "off");
   return INIT_SUCCEEDED;
}

void PlaceForToday()
{
   datetime now    = TimeCurrent();
   datetime open_t = ETTimeToServer(now, RangeEndHourET, RangeEndMinET);
   datetime stop_t = ETTimeToServer(now, CancelHourET,  CancelMinET);
   if(now < open_t || now >= stop_t) return;
   if(g_day_done == ETDate(now)) return;

   MqlDateTime dt; TimeToStruct(ServerToUTC(now), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6) { g_day_done = ETDate(now); return; }

   double or_h, or_l; string note;
   bool ok    = BuildRange(now, or_h, or_l, note);
   string etd = TimeToString(ETDate(now), TIME_DATE);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(!ok)
   {
      Append(DAY_CSV, StringFormat("%s,%s,,,,0,%s", etd, _Symbol, note));
      g_day_done = ETDate(now);
      return;
   }

   double lot = MinLot();
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   long   lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double mind = lvl * pt;
   int    placed = 0;
   string why = note;

   if(or_h - ask > mind)
   {
      if(trade.BuyStop(lot, NormalizeDouble(or_h, _Digits), _Symbol, 0, 0,
                       ORDER_TIME_SPECIFIED, stop_t, "M001")) placed++;
      else why += "|buystop err " + IntegerToString(trade.ResultRetcode());
   }
   else why += "|price already above OR high";

   if(bid - or_l > mind)
   {
      if(trade.SellStop(lot, NormalizeDouble(or_l, _Digits), _Symbol, 0, 0,
                        ORDER_TIME_SPECIFIED, stop_t, "M001")) placed++;
      else why += "|sellstop err " + IntegerToString(trade.ResultRetcode());
   }
   else why += "|price already below OR low";

   Append(DAY_CSV, StringFormat("%s,%s,%.2f,%.2f,%.2f,%d,%s",
                                etd, _Symbol, or_h, or_l, (or_h - or_l) / pt, placed, why));
   g_day_done = ETDate(now);
}

//--- close anything of ours immediately, and log what the fill cost
void FlattenAndLog()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      double   fill  = PositionGetDouble(POSITION_PRICE_OPEN);
      long     ptype = PositionGetInteger(POSITION_TYPE);
      datetime ft    = (datetime)PositionGetInteger(POSITION_TIME);
      double   vol   = PositionGetDouble(POSITION_VOLUME);
      double   pt    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double   spread_pts = (SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                             - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / pt;

      double   level = 0; datetime placed_t = 0;
      ulong    pid = PositionGetInteger(POSITION_IDENTIFIER);
      if(HistorySelectByPosition(pid))
         for(int k = 0; k < HistoryOrdersTotal(); k++)
         {
            ulong oh = HistoryOrderGetTicket(k);
            if(oh == 0) continue;
            long ot = HistoryOrderGetInteger(oh, ORDER_TYPE);
            if(ot == ORDER_TYPE_BUY_STOP || ot == ORDER_TYPE_SELL_STOP)
            {
               level    = HistoryOrderGetDouble(oh, ORDER_PRICE_OPEN);
               placed_t = (datetime)HistoryOrderGetInteger(oh, ORDER_TIME_SETUP);
            }
         }

      bool   isbuy = (ptype == POSITION_TYPE_BUY);
      double slip  = (level > 0) ? ((isbuy ? fill - level : level - fill) / pt) : 0;
      double ref   = isbuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                           : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(!trade.PositionClose(tk)) { Print("M001: close failed ", trade.ResultRetcode()); continue; }
      double exit_px   = trade.ResultPrice();
      double exit_slip = (isbuy ? ref - exit_px : exit_px - ref) / pt;

      Append(FILL_CSV, StringFormat("%s,%s,%s,%.2f,%.2f,%.2f,%d,%.2f,%.2f,%.2f,%.2f,%s",
             TimeToString(ft, TIME_DATE | TIME_SECONDS), _Symbol, isbuy ? "buy" : "sell",
             level, fill, slip, (int)(ft - placed_t), spread_pts, exit_px, exit_slip, vol,
             TimeToString(placed_t, TIME_DATE | TIME_SECONDS)));
      PrintFormat("M001 FILL %s level %.2f fill %.2f slip %.2f pts spread %.2f",
                  isbuy ? "buy" : "sell", level, fill, slip, spread_pts);
   }
}

void OnTick()
{
   FlattenAndLog();                 // never hold a position longer than one tick
   if(EnableTrading) PlaceForToday();
}
