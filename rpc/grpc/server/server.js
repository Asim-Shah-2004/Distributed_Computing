const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');
const winston = require('winston');


const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.json()
    ),
    transports: [
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' }),
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                winston.format.simple()
            )
        })
    ]
});


try {
    process.chdir(__dirname);
    logger.info(`Working directory: ${process.cwd()}`);
} catch (error) {
    logger.error('Failed to set working directory:', error);
    process.exit(1);
}


const PROTO_PATH = path.join(__dirname, 'computation.proto');
logger.info(`Loading proto file from: ${PROTO_PATH}`);

let packageDefinition;
try {
    packageDefinition = protoLoader.loadSync(PROTO_PATH, {
        keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true
    });
} catch (error) {
    logger.error('Failed to load proto file:', error);
    process.exit(1);
}

const computationProto = grpc.loadPackageDefinition(packageDefinition).computation;

const MOD = 998244353n;


function modPow(base, exp, modulus) {
    try {
        base = BigInt(base) % modulus;
        exp = BigInt(exp);
        let result = 1n;
        
        while (exp > 0n) {
            if (exp & 1n) {
                result = (result * base) % modulus;
            }
            base = (base * base) % modulus;
            exp >>= 1n;
        }
        return result;
    } catch (error) {
        logger.error('Error in modPow calculation:', error);
        throw error;
    }
}


function processTestCase(n, array) {
    try {
        logger.info(`Processing test case with n=${n}`);
        logger.debug('Input array:', array);

        const prefix = new Array(n + 1).fill(0n);
        let cnt = 0n;
        let sum = 0n;
        

        for (let i = 0; i < n; i++) {
            if (array[i] === 2) {
                prefix[i + 1] = prefix[i] + 1n;
            } else {
                prefix[i + 1] = prefix[i];
            }
            
            if (array[i] === 3) {
                cnt++;
                sum = (sum + modPow(2n, prefix[i], MOD)) % MOD;
            }
        }
        
        let ans = 0n;
        

        for (let i = 0; i < n; i++) {
            if (array[i] === 1) {
                const power = modPow(2n, prefix[i], MOD);
                const inv_power = modPow(power, MOD - 2n, MOD);
                let temp = (sum * inv_power) % MOD;
                temp = ((temp - BigInt(cnt)) % MOD + MOD) % MOD;
                ans = (ans + temp) % MOD;
            }
            if (array[i] === 3) {
                cnt--;
                sum = ((sum - modPow(2n, prefix[i], MOD)) % MOD + MOD) % MOD;
            }
        }
        
        logger.info(`Computation completed. Result: ${ans}`);
        return ans;
    } catch (error) {
        logger.error('Error in processTestCase:', error);
        throw error;
    }
}


const server = new grpc.Server();
server.addService(computationProto.Computation.service, {
    processTestCase: (call, callback) => {
        try {
            logger.info('Received gRPC request');
            logger.debug('Request payload:', call.request);

            const n = parseInt(call.request.n);
            const array = call.request.array.map(x => parseInt(x));
            
            const result = processTestCase(n, array);
            
            logger.info('Successfully processed request');
            callback(null, { answer: result.toString() });
        } catch (error) {
            logger.error('Error processing request:', error);
            callback({
                code: grpc.status.INTERNAL,
                details: 'Internal server error: ' + error.message
            });
        }
    }
});


const port = process.env.PORT || 50051;
server.bindAsync(
    `0.0.0.0:${port}`,
    grpc.ServerCredentials.createInsecure(),
    (error, boundPort) => {
        if (error) {
            logger.error('Failed to bind server:', error);
            process.exit(1);
        }
        server.start();
        logger.info(`Server running on port ${boundPort}`);
    }
);


process.on('SIGTERM', () => {
    logger.info('SIGTERM received. Shutting down gracefully...');
    server.tryShutdown(() => {
        logger.info('Server shut down complete');
        process.exit(0);
    });
});

process.on('uncaughtException', (error) => {
    logger.error('Uncaught exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    logger.error('Unhandled rejection at:', promise, 'reason:', reason);
    process.exit(1);
});