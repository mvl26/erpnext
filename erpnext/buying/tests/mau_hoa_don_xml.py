# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng XML hóa đơn điện tử mẫu (Thông tư 78) cho test tiếp nhận hóa đơn."""

from xml.sax.saxutils import escape

MST_MIYANO = "0109529507"


def xml_hoa_don(
	dong,
	so="00001234",
	ky_hieu="C26TAB",
	ngay="2026-10-23",
	mst_ban="0101234567",
	ten_ban="Công ty NCC mẫu",
	mst_mua=MST_MIYANO,
	ghi_chu="",
	tong=None,
	boc_tdiep=False,
	namespace=False,
):
	"""`dong`: [(mã, tên, ĐVT, số lượng, đơn giá, thuế suất)] hoặc thêm phần tử thứ 7 là TChat."""
	hang = []
	tien_hang = thue = 0
	for i, d in enumerate(dong, 1):
		ma, ten, dvt, sl, gia, ts = d[:6]
		tchat = d[6] if len(d) > 6 else 1
		tt = sl * gia
		if tchat == 1:
			tien_hang += tt
			thue += tt * float(str(ts).rstrip("%") or 0) / 100 if str(ts)[0].isdigit() else 0
		hang.append(
			f"<HHDVu><TChat>{tchat}</TChat><STT>{i}</STT><MHHDVu>{escape(ma)}</MHHDVu>"
			f"<THHDVu>{escape(ten)}</THHDVu><DVTinh>{escape(dvt)}</DVTinh><SLuong>{sl}</SLuong>"
			f"<DGia>{gia}</DGia><ThTien>{tt}</ThTien><TSuat>{ts}</TSuat></HHDVu>"
		)
	tong = tong or (tien_hang, thue, tien_hang + thue)
	ns = ' xmlns="http://example.invalid/hddt"' if namespace else ""
	hdon = (
		f"<HDon{ns}><DLHDon Id='data'><TTChung><PBan>2.0.0</PBan><THDon>Hóa đơn giá trị gia tăng</THDon>"
		f"<KHMSHDon>1</KHMSHDon><KHHDon>{ky_hieu}</KHHDon><SHDon>{so}</SHDon><NLap>{ngay}</NLap>"
		f"<DVTTe>VND</DVTTe><TGia>1</TGia></TTChung>"
		f"<NDHDon><NBan><Ten>{escape(ten_ban)}</Ten><MST>{mst_ban}</MST></NBan>"
		f"<NMua><Ten>Công ty TNHH Miyano Việt Nam</Ten><MST>{mst_mua}</MST></NMua>"
		f"<DSHHDVu>{''.join(hang)}</DSHHDVu>"
		f"<TToan><TgTCThue>{tong[0]}</TgTCThue><TgTThue>{tong[1]}</TgTThue>"
		f"<TgTTTBSo>{tong[2]}</TgTTTBSo></TToan></NDHDon>"
		f"<TTKhac><TTin><TTruong>Ghi chú</TTruong><KDLieu>string</KDLieu><DLieu>{escape(ghi_chu)}</DLieu></TTin></TTKhac>"
		f"</DLHDon><MCCQT>00ABCDEF</MCCQT></HDon>"
	)
	if boc_tdiep:
		hdon = f"<TDiep><TTChung><MNGui>K0109529507</MNGui></TTChung><DLieu>{hdon}</DLieu></TDiep>"
	return ('<?xml version="1.0" encoding="UTF-8"?>' + hdon).encode()
