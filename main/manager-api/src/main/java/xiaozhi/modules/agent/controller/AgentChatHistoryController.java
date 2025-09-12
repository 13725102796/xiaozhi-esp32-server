package xiaozhi.modules.agent.controller;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import jakarta.validation.constraints.NotBlank;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import xiaozhi.common.utils.Result;
import xiaozhi.modules.agent.dto.AgentChatHistoryReportDTO;
import xiaozhi.modules.agent.dto.MacAddressReplaceDTO;
import xiaozhi.modules.agent.service.biz.AgentChatHistoryBizService;

@Tag(name = "智能体聊天历史管理")
@RequiredArgsConstructor
@RestController
@RequestMapping("/agent/chat-history")
public class AgentChatHistoryController {
    private final AgentChatHistoryBizService agentChatHistoryBizService;

    /**
     * 小智服务聊天上报请求
     * <p>
     * 小智服务聊天上报请求，包含Base64编码的音频数据和相关信息。
     *
     * @param request 包含上传文件及相关信息的请求对象
     */
    @Operation(summary = "小智服务聊天上报请求")
    @PostMapping("/report")
    public Result<Boolean> uploadFile(@Valid @RequestBody AgentChatHistoryReportDTO request) {
        Boolean result = agentChatHistoryBizService.report(request);
        return new Result<Boolean>().ok(result);
    }

    /**
     * 替换聊天记录中的MAC地址
     * <p>
     * 将指定MAC地址的所有聊天记录更新为新的MAC地址
     * 支持任意格式的MAC地址标识符，包括带前缀ID的格式（如：7371826811379920896F2:EE:07:4A:03:14）
     *
     * @param macAddress 原MAC地址（支持任意格式，包括ID前缀）
     * @param newMacAddress 新MAC地址（支持任意格式，包括ID前缀）
     */
    @Operation(summary = "替换聊天记录MAC地址")
    @PostMapping("/replace-mac-address")
    public Result<Boolean> replaceMacAddress(@RequestParam(required = false) String macAddress, 
                                           @RequestParam(required = false) String newMacAddress) {
        // 在Controller层进行参数校验，提供更友好的错误信息
        if (macAddress == null || macAddress.trim().isEmpty()) {
            return new Result<Boolean>().error("原MAC地址参数不能为空");
        }
        if (newMacAddress == null || newMacAddress.trim().isEmpty()) {
            return new Result<Boolean>().error("新MAC地址参数不能为空");
        }
        
        Boolean result = agentChatHistoryBizService.replaceMacAddress(macAddress, newMacAddress);
        return new Result<Boolean>().ok(result);
    }

    /**
     * 替换聊天记录中的MAC地址 (JSON接口)
     * <p>
     * 将指定MAC地址的所有聊天记录更新为新的MAC地址
     * 支持任意格式的MAC地址标识符，包括带前缀ID的格式
     *
     * @param request MAC地址替换请求对象
     */
    @Operation(summary = "替换聊天记录MAC地址(JSON)")
    @PostMapping("/replace-mac-address-json")
    public Result<Boolean> replaceMacAddressJson(@RequestBody MacAddressReplaceDTO request) {
        // 参数校验
        if (request == null) {
            return new Result<Boolean>().error("请求参数不能为空");
        }
        if (request.getMacAddress() == null || request.getMacAddress().trim().isEmpty()) {
            return new Result<Boolean>().error("原MAC地址参数不能为空");
        }
        if (request.getNewMacAddress() == null || request.getNewMacAddress().trim().isEmpty()) {
            return new Result<Boolean>().error("新MAC地址参数不能为空");
        }
        
        Boolean result = agentChatHistoryBizService.replaceMacAddress(request.getMacAddress(), request.getNewMacAddress());
        return new Result<Boolean>().ok(result);
    }
}
