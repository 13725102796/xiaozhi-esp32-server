package xiaozhi.modules.agent;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import xiaozhi.modules.agent.service.AgentChatHistoryService;
import xiaozhi.modules.agent.service.biz.AgentChatHistoryBizService;

import static org.junit.jupiter.api.Assertions.*;

/**
 * MAC地址替换功能测试
 */
@SpringBootTest
public class AgentChatHistoryMacAddressReplaceTest {

    @Autowired
    private AgentChatHistoryService agentChatHistoryService;
    
    @Autowired
    private AgentChatHistoryBizService agentChatHistoryBizService;

    @Test
    @Transactional
    public void testReplaceMacAddress() {
        // 测试标准MAC地址格式
        String oldMacAddress = "AA:BB:CC:DD:EE:FF";
        String newMacAddress = "11:22:33:44:55:66";
        
        // 调用业务层方法
        Boolean result = agentChatHistoryBizService.replaceMacAddress(oldMacAddress, newMacAddress);
        
        // 验证结果
        assertNotNull(result);
        assertTrue(result);
    }
    
    @Test
    @Transactional
    public void testReplaceMacAddressWithIdPrefix() {
        // 测试带ID前缀的MAC地址格式
        String oldMacAddress = "7371826811379920896F2:EE:07:4A:03:14";
        String newMacAddress = "9876543210123456789AA:BB:CC:DD:EE:FF";
        
        // 调用业务层方法
        Boolean result = agentChatHistoryBizService.replaceMacAddress(oldMacAddress, newMacAddress);
        
        // 验证结果
        assertNotNull(result);
        assertTrue(result);
    }
    
    @Test
    @Transactional
    public void testReplaceMacAddressWithSameValue() {
        // 测试参数相同的情况
        String macAddress = "AA:BB:CC:DD:EE:FF";
        
        // 调用业务层方法
        Boolean result = agentChatHistoryBizService.replaceMacAddress(macAddress, macAddress);
        
        // 验证结果
        assertNotNull(result);
        assertTrue(result);
    }
    
    @Test
    @Transactional
    public void testReplaceMacAddressWithNullValues() {
        // 测试空值参数
        Boolean result1 = agentChatHistoryBizService.replaceMacAddress(null, "11:22:33:44:55:66");
        Boolean result2 = agentChatHistoryBizService.replaceMacAddress("AA:BB:CC:DD:EE:FF", null);
        Boolean result3 = agentChatHistoryBizService.replaceMacAddress("", "11:22:33:44:55:66");
        Boolean result4 = agentChatHistoryBizService.replaceMacAddress("AA:BB:CC:DD:EE:FF", "");
        
        // 验证结果
        assertFalse(result1);
        assertFalse(result2);
        assertFalse(result3);
        assertFalse(result4);
    }
}