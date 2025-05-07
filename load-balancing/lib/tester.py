import requests
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tabulate import tabulate
from statistics import mean, median, stdev
from lib.utils import setup_logging

class LoadBalancerTester:
    def __init__(self, url, num_requests=200):
        self.url = url
        self.num_requests = num_requests
        self.results = []
        self.response_times = []
        self.start_time = None
        self.end_time = None
        self.logger = setup_logging("LoadBalancerTester")

    def _send_request(self, i):
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                start = time.time()
                response = requests.get(
                    f"{self.url}?cache_bust={i}", 
                    timeout=5,
                    headers={'Connection': 'close'}
                )
                response_time = time.time() - start
                response.raise_for_status()
                result = response.json()
                result['response_time'] = response_time
                return result
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"⚠️ Request {i} failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return {"error": str(e), "response_time": time.time() - start}
            except Exception as e:
                self.logger.error(f"❌ Unexpected error in request {i}: {str(e)}")
                return {"error": str(e), "response_time": time.time() - start}

    def run(self):
        self.logger.info(f"🚀 Starting load test with {self.num_requests} requests to {self.url}")
        self.start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._send_request, i) 
                      for i in range(self.num_requests)]
            self.results = [f.result() for f in futures]
        self.end_time = time.time()
        self.logger.info("✅ Load test completed")
        return self.results

    def _calculate_percentile(self, data, percentile):
        if not data:
            return 0
        sorted_data = sorted(data)
        index = (len(sorted_data) - 1) * percentile / 100
        floor = int(index)
        ceil = min(floor + 1, len(sorted_data) - 1)
        if floor == ceil:
            return sorted_data[floor]
        d = index - floor
        return sorted_data[floor] * (1 - d) + sorted_data[ceil] * d

    def analyze(self):
        self.logger.info("📊 Analyzing load test results...")
        
        # Basic stats
        stats = {
            "success": 0,
            "errors": 0,
            "servers": {},
            "total_requests": self.num_requests,
            "response_times": [],
            "error_messages": {}
        }
        
        # Process results
        for result in self.results:
            if "error" in result:
                stats["errors"] += 1
                error_msg = str(result["error"])
                stats["error_messages"][error_msg] = stats["error_messages"].get(error_msg, 0) + 1
            else:
                stats["success"] += 1
                server_id = result.get("server_id", "unknown")
                stats["servers"][server_id] = stats["servers"].get(server_id, 0) + 1
                if "response_time" in result:
                    stats["response_times"].append(result["response_time"])

        # Calculate metrics
        test_duration = self.end_time - self.start_time
        stats["metrics"] = {
            "test_duration": test_duration,
            "requests_per_second": self.num_requests / test_duration if test_duration > 0 else 0,
            "error_rate": (stats["errors"] / self.num_requests) * 100 if self.num_requests > 0 else 0,
            "success_rate": (stats["success"] / self.num_requests) * 100 if self.num_requests > 0 else 0
        }

        # Response time statistics
        if stats["response_times"]:
            stats["response_time_stats"] = {
                "min": min(stats["response_times"]),
                "max": max(stats["response_times"]),
                "mean": mean(stats["response_times"]),
                "median": median(stats["response_times"]),
                "p95": self._calculate_percentile(stats["response_times"], 95),
                "p99": self._calculate_percentile(stats["response_times"], 99),
                "std_dev": stdev(stats["response_times"]) if len(stats["response_times"]) > 1 else 0
            }

        # Calculate distribution
        if stats["success"] > 0:
            stats["distribution"] = {
                server_id: (count / stats["success"]) * 100
                for server_id, count in stats["servers"].items()
            }

        # Generate report
        report = self._generate_report(stats)
        self._save_report(report, stats)
        
        return stats

    def _generate_report(self, stats):
        # Create tables for different metrics
        tables = []
        
        # Summary table
        summary_data = [
            ["Total Requests", stats["total_requests"]],
            ["Successful Requests", stats["success"]],
            ["Failed Requests", stats["errors"]],
            ["Success Rate", f"{stats['metrics']['success_rate']:.2f}%"],
            ["Error Rate", f"{stats['metrics']['error_rate']:.2f}%"],
            ["Requests per Second", f"{stats['metrics']['requests_per_second']:.2f}"],
            ["Test Duration", f"{stats['metrics']['test_duration']:.2f}s"]
        ]
        tables.append(("Summary", summary_data))

        # Response time table
        if "response_time_stats" in stats:
            rt_stats = stats["response_time_stats"]
            rt_data = [
                ["Min", f"{rt_stats['min']*1000:.2f}ms"],
                ["Max", f"{rt_stats['max']*1000:.2f}ms"],
                ["Mean", f"{rt_stats['mean']*1000:.2f}ms"],
                ["Median", f"{rt_stats['median']*1000:.2f}ms"],
                ["95th Percentile", f"{rt_stats['p95']*1000:.2f}ms"],
                ["99th Percentile", f"{rt_stats['p99']*1000:.2f}ms"],
                ["Standard Deviation", f"{rt_stats['std_dev']*1000:.2f}ms"]
            ]
            tables.append(("Response Time Statistics", rt_data))

        # Server distribution table
        if "distribution" in stats:
            dist_data = [[server, f"{percentage:.2f}%"] 
                        for server, percentage in stats["distribution"].items()]
            tables.append(("Server Distribution", dist_data))

        # Error analysis table
        if stats["error_messages"]:
            error_data = [[msg, count] for msg, count in stats["error_messages"].items()]
            tables.append(("Error Analysis", error_data))

        # Format all tables
        formatted_tables = []
        for title, data in tables:
            table = tabulate(data, headers=["Metric", "Value"], tablefmt="grid")
            formatted_tables.append(f"\n{title}\n{table}")

        return "\n".join(formatted_tables)

    def _save_report(self, report, stats):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_report_{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write(f"Load Test Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"URL: {self.url}\n")
            f.write(f"Total Requests: {self.num_requests}\n")
            f.write("=" * 80 + "\n\n")
            f.write(report)
            
            # Save raw stats as JSON for further analysis
            json_filename = f"load_test_stats_{timestamp}.json"
            with open(json_filename, "w") as jf:
                json.dump(stats, jf, indent=2)
        
        self.logger.info(f"📝 Report saved to {filename}")
        self.logger.info(f"📊 Raw stats saved to {json_filename}")