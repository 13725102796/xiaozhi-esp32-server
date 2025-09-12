package xiaozhi.modules.agent.dto;

import lombok.Data;

/**
 * MAC地址替换请求DTO
 */
@Data
public class MacAddressReplaceDTO {
    /**
     * 原MAC地址（支持任意格式，包括ID前缀）
     */
    private String macAddress;
    
    /**
     * 新MAC地址（支持任意格式，包括ID前缀）
     */
    private String newMacAddress;
}