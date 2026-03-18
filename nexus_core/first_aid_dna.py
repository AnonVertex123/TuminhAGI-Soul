import re
import os

class GlobalEmergencyLocator:
    """
    Detects current location and returns the corresponding medical emergency hotline.
    Optimized for zero-delay retrieval.
    """
    GLOBAL_HOTLINES = {
        "VN": "115",
        "US": "911",
        "EU": "112",
        "UK": "999",
        "AU": "000",
        "JP": "119",
        "KR": "119",
        "IN": "102"
    }

    @staticmethod
    def get_local_hotline() -> str:
        """
        Detects current position via SYSTEM_LOCALE env or falls back to VN (115).
        """
        # Można tu dodać detekcję przez timezone jeśli środowisko na to pozwala
        current_locale = os.environ.get("SYSTEM_LOCALE", "VN").upper()
        return GlobalEmergencyLocator.GLOBAL_HOTLINES.get(current_locale, "115")

class SpinalReflexEngine:
    """
    TuminhAGI 'Spinal Reflex Engine' - Unconditional reflex for life-critical situations.
    Bypasses LLM reasoning (latency < 10ms) with high-priority protocols.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpinalReflexEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
            
        # VITAL_FIRST_AID_DB: In-memory core emergency protocols with dynamic hotline interpolation.
        self.VITAL_FIRST_AID_DB = {
            "ran_can": "🚨 [PHẢN XẠ TỦY SỐNG]: 1. Giữ nạn nhân bình tĩnh, bất động chi bị cắn thấp hơn tim. 2. KHÔNG rạch, hút nọc hay garo. 3. Gọi ngay {hotline} lập tức hoặc đến cơ sở y tế gần nhất.",
            "ngung_tho_ngung_tim": "🚨 [PHẢN XẠ TỦY SỐNG]: 1. Gọi ngay {hotline} khẩn cấp ngay lập tức. 2. Ép tim ngoài lồng ngực mạnh/nhanh (100-120 lần/phút) ở giữa ngực. 3. 30 lần ép tim : 2 lần thổi ngạt.",
            "ngat_xiu_hon_me": "🚨 [PHẢN XẠ TỦY SỐNG]: 1. Đặt nằm nghiêng an toàn (Sơ cứu). 2. Thông thoáng đường thở. 3. Nới lỏng quần áo và gọi {hotline}.",
            "chay_mau_o_at": "🚨 [PHẢN XẠ TỦY SỐNG]: 1. Ấn trực tiếp vết thương bằng vải/gạc sạch. 2. Duy trì áp lực liên tục. 3. Gọi {hotline} và dùng garo nếu chảy máu chi không kiểm soát được."
        }
        
        # Regex map for trigger-word detection.
        self.reflex_map = {
            r"rắn cắn|snake bite": "ran_can",
            r"ngừng thở|ngưng tim|cardiac arrest|CPR|ép tim": "ngung_tho_ngung_tim",
            r"ngất xỉu|hôn mê|unconscious": "ngat_xiu_hon_me",
            r"chảy máu ồ ạt|đứt động mạch|severe bleeding": "chay_mau_o_at"
        }
        
        self._initialized = True

    def intercept_prompt(self, user_input: str) -> str:
        """
        Scans input for life-threatening keywords and returns formatted action list instantly.
        """
        hotline = GlobalEmergencyLocator.get_local_hotline()
        for pattern, db_key in self.reflex_map.items():
            if re.search(pattern, user_input, re.IGNORECASE):
                protocol_template = self.VITAL_FIRST_AID_DB.get(db_key)
                return protocol_template.format(hotline=hotline)
        return None
