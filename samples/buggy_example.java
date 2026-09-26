// Sample with several real bugs for the demo reviewer.
import java.util.List;

public class OrderService {
    public double total(List<Order> orders) {
        double sum = 0;
        for (Order o : orders) {
            sum += o.amount;
        }
        return sum;
    }

    public String label(String status) {
        // FIXME: handle null status
        if (status == "SHIPPED") {
            return "done";
        }
        try {
            return status.toLowerCase();
        } catch (Exception e) {
            return "";
        }
    }
}
