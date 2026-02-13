import json
from typing import List
import requests
from pydantic import BaseModel
import time

class CurrentDateRootInfo(BaseModel):
    msgID: str


class CURRENT(BaseModel):
    DATE: str


class CurrentDateResult(BaseModel):
    root_info: CurrentDateRootInfo
    CURRENT: CURRENT


class ExchanteRateRootInfo(BaseModel):
    serviceList: str
    useRD: str
    afterEJBCall: str
    userCallback: str
    action: str
    clearTarget: str
    redirectURL: str
    pushRcvKey: str
    requestMessage: str
    bodyLengthSize: str
    useSign: str
    exceptionCallback: str
    keepTransactionSession: str
    bodyLengthOffset: str
    pushSndKey: str
    nextServiceCode: str
    showjstarerror: str
    signCode: str
    filterStr: str
    permitMultiTransaction: str
    encryptionKey2: str
    beforeEJBCall: str
    useCert: str
    language: str
    pushGuestService: str
    headerSize: str
    debug: str
    cacheService: str
    beforeServletCall: str
    errorurl: str
    pushSndOtherKey: str
    RDType: str
    exE2E: str
    hideProcess: str
    callBack: str
    encryptionKey: str
    _signData: str
    serviceCode: str
    responseMessage: str
    task: str
    requestType: str
    TRUSTEERKEY: str
    gwc_channel_gbn: str
    msgID: str
    gwc_menu_gbn: str
    useRDC: str
    afterServletCall: str


class RGIBC01601Item(BaseModel):
    tc_sel_rt: str
    sh_lcl_corp_c_getSession: str
    coin_sel_rt_originalValue: str
    number_separate: str
    crsrt_rt: str
    pos_sel_cent_rt: str
    coin_buy_rt: str
    tt_buy_rt_originalValue: str
    cash_buy_rt: str
    pos_sel_cent_rt_originalValue: str
    crsrt_rt_originalValue: str
    tc_buy_rt_originalValue: str
    selbuy_stnd_rt: str
    tt_sel_rt_originalValue: str
    tt_buy_rt: str
    tc_buy_rt: str
    cash_buy_rt_originalValue: str
    coin_sel_rt: str
    pos_buy_cent_rt_originalValue: str
    tc_sel_rt_originalValue: str
    cash_sel_rt: str
    ccy_c_display: str
    decimal_point: str
    coin_buy_rt_originalValue: str
    selbuy_stnd_rt_originalValue: str
    decimal_point_getSession: str
    cash_sel_rt_originalValue: str
    number_separate_getSession: str
    pos_buy_cent_rt: str
    sh_lcl_corp_c: str
    ccy_c: str
    tt_sel_rt: str


class RGIBC0160(BaseModel):
    gwc_ipaddr_2: str
    gwc_ef_time: str
    gwc_ipaddr: str
    gwc_cusno: str
    gwc_ef_date: str
    gwc_ef_serial: str
    gwc_sec_chk: str
    ntfct_dt_originalValue: str
    gwc_endmark: str
    gwc_gmt_time_originalValue: str
    gwc_login_type: str
    ntfct_dt: str
    gwc_hybrid_gbn: str
    gwc_sub_domain: str
    gwc_intnbk_trx_mng_no: str
    gwc_web_domain: str
    inf_regis_time: str
    gwc_sh_group_code: str
    gwc_sysgbn: str
    gwc_web_time: str
    gwc_sec_chal_getSession: str
    gwc_mac_2: str
    gwc_spare: str
    gwc_mac_1: str
    gwc_gmt_time: str
    gwc_resultcd: str
    gwc_web_date: str
    gwc_ichepswd_chk: str
    gwc_gmt_date_originalValue: str
    gwc_gmt_date: str
    gwc_pktlen: str
    gwc_ef_yoil: str
    gwc_upmu_kbn: str
    gwc_jstar_value: str
    gwc_sec_chal: str
    gwc_self: str
    gwc_user_id: str
    inf_regis_time_originalValue: str
    grid_cnt_01: str
    ntfct_odr: str
    gwc_language: str
    gwc_channel_gbn: str
    gwc_kyul_gbn: str
    gwc_ipaddr_2_getSession: str
    gwc_svc_code: str
    gwc_rrno: str


class ExchanteRateResult(BaseModel):
    root_info: ExchanteRateRootInfo
    R_GIBC0160_1: List[RGIBC01601Item]
    R_GIBC0160: RGIBC0160


class ShinhanhBankExchangeRate:
    def __init__(self):
        pass

    def get_current_exchange_rate(self):
        idx = time.time_ns()
        URL1 = f"https://online.shinhan.com.vn/common/jsp/callGibJsonCurrentDateTime.jsp?type=&pattern=yyyyMMdd&c_time=idx{idx}"
        URL2 = f"https://online.shinhan.com.vn/common/jsp/callGibJsonGuestCommonService.jsp?documentUrl=undefined&idx={idx}"
        session = requests.Session()
        session.get("https://online.shinhan.com.vn/global.shinhan")
        data1 = session.post(
            URL1,
            headers={"accept": "application/json; charset=UTF-8"},
            json={"gwc_channel_gbn": "D2", "gwc_menu_gbn": "0"},
        )

        current_date = CurrentDateResult(**data1.json())

        data2 = session.post(
            URL2,
            headers={
                "accept": "application/json; charset=UTF-8",
            },
            data={
                "plainJSON": json.dumps(
                    {
                        "root_info": {
                            "msgID": "S_GIBC0160",
                            "requestType": "doGuestJSON",
                            "callBack": "gibObj.doC0160Callback",
                            "userCallback": "",
                            "debug": "",
                            "useSign": "",
                            "useCert": "",
                            "language": "ko",
                            "errorurl": "",
                            "task": "",
                            "action": "",
                            "signCode": "",
                            "serviceCode": "C0160",
                            "requestMessage": "S_GIBC0160",
                            "responseMessage": "R_GIBC0160",
                            "exceptionCallback": "gibObj.doC0160Callback",
                            "showjstarerror": "",
                            "_signData": "",
                            "keepTransactionSession": "",
                            "permitMultiTransaction": "",
                            "clearTarget": 'data:json,[{"id":"dm_R_GIBC0160","key":"R_GIBC0160"},{"id":"dl_R_GIBC0160_1","key":"R_GIBC0160_1"}]',
                            "encryptionKey": "",
                            "encryptionKey2": "",
                            "redirectURL": "",
                            "exE2E": "",
                            "filterStr": "",
                            "nextServiceCode": "",
                            "serviceList": "",
                            "hideProcess": "false",
                            "useRD": "",
                            "useRDC": "",
                            "gwc_channel_gbn": "D2",
                            "gwc_menu_gbn": "0",
                            "RDType": "",
                            "TRUSTEERKEY": "",
                            "cacheService": "",
                            "pushSndKey": "",
                            "pushSndOtherKey": "",
                            "pushRcvKey": "",
                            "pushGuestService": "",
                        },
                        "S_GIBC0160": {
                            "sh_lcl_corp_c": "130",
                            "ntfct_dt": current_date.CURRENT.DATE,
                            "ccy_c": "",
                            "ntfct_odr": "999",
                            "exrt_inq_d": "1",
                        },
                    }
                )
            },
        )

        exrate = ExchanteRateResult(**data2.json())
        data = {}
        for rate in exrate.R_GIBC0160_1:
            data[rate.ccy_c] = float(rate.tt_sel_rt_originalValue)

        return data


if __name__ == "__main__":
    exrate = ShinhanhBankExchangeRate()
    exrate.get_current_exchange_rate()
