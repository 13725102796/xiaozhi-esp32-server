@ -0,0 +1,42 @@
package xiaozhi.modules.device.dto;

import java.io.Serializable;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 设备恢复出厂设置DTO
 * 用于清空指定设备的所有使用数据，恢复到刚绑定时的初始状态
 */
@Data
@Schema(description = "设备恢复出厂设置对象")
public class DeviceResetDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @Schema(description = "设备MAC地址", example = "AA:BB:CC:DD:EE:FF")
    @NotBlank(message = "设备MAC地址不能为空")
    @Pattern(regexp = "^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", 
             message = "MAC地址格式不正确")
    private String macAddress;

    @Schema(description = "重置确认码(防误操作,格式: RESET_xxxxxxx)", example = "RESET_123456")
    @NotBlank(message = "确认码不能为空")
    @Pattern(regexp = "^RESET_.{6,}$", 
             message = "确认码格式不正确，应以RESET_开头且至少6位字符")
    private String confirmationCode;

    @Schema(description = "重置原因说明", example = "清理测试数据")
    private String reason;

    @Schema(description = "是否重置声纹信息", example = "true", defaultValue = "true")
    private Boolean resetVoiceprint = true;

    @Schema(description = "是否重置智能体记忆", example = "true", defaultValue = "true")
    private Boolean resetMemory = true;

    @Schema(description = "是否重置聊天记录", example = "true", defaultValue = "true")
    private Boolean resetChatHistory = true;
}